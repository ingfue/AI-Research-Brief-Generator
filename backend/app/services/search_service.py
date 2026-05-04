"""
Azure AI Search service for indexing and querying HubSpot deal chunks.

Two-tier indexing pipeline:

  Tier 1 — Fine-grained structural sub-chunks
    1a. Parse deal metadata into sub-chunks (identity, scope, logistics)
    1b. Split email bodies into paragraph / numbered-item sub-chunks
    1c. Split meeting notes into heading-level sub-chunks
    1d. Convert brief_requirements into a natural-language additional_info chunk
    2.  Enrich each sub-chunk via Azure AI Language (key phrases, entities, sentiment)
    3.  Classify each sub-chunk by brief section relevance (section_tags) via Azure OpenAI
    4.  Extract potential research questions from each sub-chunk via Azure OpenAI
    5.  Generate vector embeddings via Azure OpenAI

  Tier 2 — Section aggregate chunks
    6.  Group all Tier 1 sub-chunks by section_tag
    7.  Assemble one aggregate chunk per template section (de-duplicated view)
    8.  Enrich, embed, and push aggregate chunks alongside Tier 1

  Final: Push all documents to the search index
"""

import re as _re
import uuid
import json
import logging
from collections import defaultdict
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SimpleField,
    SearchableField,
    SearchFieldDataType,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
)
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from app.config import get_settings
from app.services.enrichment_service import EnrichmentService

logger = logging.getLogger(__name__)


EMBEDDING_DIMENSIONS = 1536


class SearchService:
    def __init__(self):
        settings = get_settings()
        credential = AzureKeyCredential(settings.azure_search_admin_key)
        self._index_client = SearchIndexClient(
            endpoint=settings.azure_search_endpoint,
            credential=credential,
        )
        self._search_client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=credential,
        )
        self._index_name = settings.azure_search_index_name
        self._enrichment = EnrichmentService()

        self._openai_endpoint = settings.azure_openai_endpoint
        self._openai_key = settings.azure_openai_key
        self._embedding_deployment = settings.azure_openai_embedding_deployment
        self._openai_client = AzureOpenAI(
            api_key=self._openai_key,
            api_version="2024-06-01",
            azure_endpoint=self._openai_endpoint,
        )

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def recreate_index(self):
        """Drop and recreate the search index (use after schema changes)."""
        try:
            self._index_client.delete_index(self._index_name)
            logger.info(f"Deleted existing index: {self._index_name}")
        except Exception:
            pass
        self._create_index()

    def ensure_index(self):
        """Create the search index if it doesn't exist."""
        try:
            self._index_client.get_index(self._index_name)
            return
        except Exception:
            pass
        self._create_index()

    def _create_index(self):

        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(name="hnsw-config"),
            ],
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-config",
                    vectorizer_name="openai-vectorizer",
                ),
            ],
            vectorizers=[
                AzureOpenAIVectorizer(
                    vectorizer_name="openai-vectorizer",
                    parameters=AzureOpenAIVectorizerParameters(
                        resource_url=self._openai_endpoint,
                        deployment_name=self._embedding_deployment,
                        model_name=self._embedding_deployment,
                        api_key=self._openai_key,
                    ),
                ),
            ],
        )

        semantic_config = SemanticConfiguration(
            name="default",
            prioritized_fields=SemanticPrioritizedFields(
                content_fields=[SemanticField(field_name="content")],
                keywords_fields=[SemanticField(field_name="keyphrases")],
                title_field=SemanticField(field_name="subject"),
            ),
        )

        index = SearchIndex(
            name=self._index_name,
            fields=[
                SimpleField(name="chunk_id", type=SearchFieldDataType.String, key=True),
                SimpleField(name="session_id", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="chunk_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SearchableField(name="content", type=SearchFieldDataType.String),
                SimpleField(name="timestamp", type=SearchFieldDataType.String, sortable=True),
                SimpleField(name="direction", type=SearchFieldDataType.String, filterable=True),
                SearchableField(name="subject", type=SearchFieldDataType.String),
                SearchableField(name="participants", type=SearchFieldDataType.String),

                # Tier hierarchy fields
                SimpleField(name="chunk_tier", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="parent_chunk_id", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="source_activity_id", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="paragraph_index", type=SearchFieldDataType.Int32, sortable=True),

                # Vector field for content embeddings
                SearchField(
                    name="content_vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=EMBEDDING_DIMENSIONS,
                    vector_search_profile_name="vector-profile",
                ),

                # Enrichment fields (populated by Azure AI Language)
                SearchableField(name="keyphrases", type=SearchFieldDataType.String),
                SearchableField(name="entities", type=SearchFieldDataType.String),
                SimpleField(name="sentiment", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="sentiment_positive", type=SearchFieldDataType.Double, filterable=True),
                SimpleField(name="sentiment_neutral", type=SearchFieldDataType.Double, filterable=True),
                SimpleField(name="sentiment_negative", type=SearchFieldDataType.Double, filterable=True),

                # Research question detection (populated by LLM during indexing)
                SearchableField(name="potential_research_questions", type=SearchFieldDataType.String),

                # Section-level content tags (populated by LLM during indexing)
                SearchField(
                    name="section_tags",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                    searchable=True,
                    filterable=True,
                    facetable=True,
                ),
            ],
            vector_search=vector_search,
            semantic_search=SemanticSearch(configurations=[semantic_config]),
        )
        self._index_client.create_index(index)
        logger.info(f"Created search index: {self._index_name}")

    # ------------------------------------------------------------------
    # Section tag classification
    # ------------------------------------------------------------------

    VALID_SECTION_TAGS = [
        "client_brand",
        "project_overview",
        "objectives",
        "research_questions",
        "data_timeframe",
        "research_usage",
        "deliverables",
        "timeline",
        "key_assumptions",
        "additional_info",
        "metadata",
    ]

    _SECTION_TAG_PROMPT = (
        "You are classifying text from client communications (emails, meetings, deal data) "
        "for a research brief. Determine which sections of the brief this text is relevant to.\n\n"
        "Available section tags:\n"
        "- client_brand: ANY mention of the client company name, brand name, product name, "
        "industry, or the contact people at the client. Examples: company identity, "
        "'Earth's Own', 'oat milk', 'Senior Brand Manager', industry like 'CPG / Beverage'. "
        "This tag should ALWAYS be applied alongside 'metadata' for deal identity chunks.\n"
        "- project_overview: describes the research purpose, strategic context, or background. "
        "Also includes competitor scope (must-have vs nice-to-have competitors, tiered competitor lists)\n"
        "- objectives: states goals the client wants to achieve (drive traffic, brand awareness, etc.)\n"
        "- research_questions: contains explicit or implicit research questions. Also includes "
        "competitor prioritization (must-have vs nice-to-have), channel priorities, and specific "
        "topics or angles the client wants investigated\n"
        "- data_timeframe: mentions date ranges, timeframes, or periods to analyze\n"
        "- research_usage: describes WHO will use the research, what DECISIONS it will inform, "
        "or the AUDIENCE for the outputs. Trigger phrases include: 'leadership-ready', "
        "'share internally', 'inform launch strategy', 'inform decisions', 'guide decisions', "
        "'used by [person/role]', 'we can share', 'present to leadership'. "
        "Also applies when content describes the business context for WHY the research is needed "
        "(e.g. 'preparing for a launch', 'want to know where to place bets')\n"
        "- deliverables: mentions expected output formats (presentations, summaries, reports), "
        "specific named sections the client wants in the output (e.g. 'include a section called X'), "
        "or any structural/content requests for the final deliverable\n"
        "- timeline: mentions project dates, deadlines, milestones, kickoff, or scheduling\n"
        "- key_assumptions: mentions scope exclusions, revision expectations, or constraints. "
        "IMPORTANT: also includes implicit scope signals like channels the client is 'less focused on', "
        "things they 'don't care about', deprioritized areas, or conditional inclusions "
        "(e.g. 'unless you see a meaningful spike')\n"
        "- additional_info: extra strategic context, leadership priorities, special requests, "
        "supplementary notes, or stakeholder color/commentary that adds nuance beyond the core "
        "project scope. Trigger phrases: 'adding more color', 'leadership is focused on', "
        "'what leadership cares about', 'if possible include', 'extra context', "
        "'success criteria', 'preferred tone', 'format sections'. "
        "Also includes brief_requirements (tone preferences, expected output structure) "
        "and any email that provides supplementary strategic direction from stakeholders.\n"
        "- metadata: contains structured deal info like contact names, budget, owner\n\n"
        "CRITICAL RULES:\n"
        "- A single text can have MULTIPLE tags — assign ALL that apply. Be generous with tags.\n"
        "- Any text that names the client company or its product MUST include \"client_brand\".\n"
        "- Any text that mentions who will see/use the outputs or why the research is needed "
        "MUST include \"research_usage\".\n"
        "- Competitor lists with priority tiers (must-have, nice-to-have) should get BOTH "
        "\"project_overview\" AND \"research_questions\".\n"
        "- Channel de-prioritizations ('less focused on X', 'don't need Y') MUST get \"key_assumptions\".\n"
        "- Requests for specific named output sections MUST get \"deliverables\".\n"
        "- Deal identity chunks (company name, contact, industry) MUST get BOTH \"client_brand\" AND \"metadata\".\n"
        "- Emails that provide extra stakeholder context, leadership priorities, or success criteria "
        "MUST include \"additional_info\" IN ADDITION to any other relevant tags.\n"
        "- Stakeholder emails that express leadership questions or priorities about channels, messaging, "
        "competitive positioning, or strategic focus areas (e.g. 'Where should we place our bets?', "
        "'What messages are landing?', 'What should we avoid?') MUST also include \"research_questions\" "
        "because these are implicit research questions the deliverable needs to answer.\n"
        "- Brief requirements or tone/format preferences MUST include \"additional_info\".\n\n"
        "Return ONLY the relevant tags as a JSON array of strings. "
        "Example: [\"client_brand\", \"metadata\", \"additional_info\"]\n"
        "If nothing clearly matches, return: [\"additional_info\"]"
    )

    def _classify_section_tags(self, texts: list[str]) -> list[list[str]]:
        """
        Use Azure OpenAI chat to classify each chunk by which brief
        sections it is relevant to. Returns a list of tag lists.
        """
        settings = get_settings()
        results: list[list[str]] = []

        for text in texts:
            if not text or not text.strip():
                results.append([])
                continue

            truncated = text[:4000]
            try:
                response = self._openai_client.chat.completions.create(
                    model=settings.azure_openai_chat_deployment,
                    messages=[
                        {"role": "system", "content": self._SECTION_TAG_PROMPT},
                        {"role": "user", "content": truncated},
                    ],
                    temperature=0.0,
                    max_tokens=150,
                )
                raw = response.choices[0].message.content.strip()
                tags = json.loads(raw)
                validated = [t for t in tags if t in self.VALID_SECTION_TAGS]
                results.append(validated if validated else ["additional_info"])
            except Exception as e:
                logger.warning(f"Section tag classification failed for chunk: {e}")
                results.append(["additional_info"])

        return results

    # ------------------------------------------------------------------
    # Research question extraction
    # ------------------------------------------------------------------

    _QUESTION_EXTRACTION_PROMPT = (
        "You are analyzing text from client communications (emails, meetings, deal data) "
        "for a research brief. Extract ALL potential research questions — both explicit "
        "questions (with ?) and implicit ones (statements where the client expresses a need "
        "to understand, learn, explore, or investigate something).\n\n"
        "Look for patterns like:\n"
        "- Direct questions about audiences, markets, competitors, channels\n"
        "- 'We want to understand / know / explore / figure out...'\n"
        "- 'Can we find out...', 'We need insight into...'\n"
        "- Requests for data, benchmarks, or comparisons\n"
        "- Stated goals that imply a research question\n\n"
        "Return ONLY the extracted questions, one per line, each prefixed with '- '. "
        "Rephrase implicit needs as proper research questions ending with '?'. "
        "If there are no potential research questions in the text, return exactly: NONE"
    )

    def _extract_potential_questions(self, texts: list[str]) -> list[str]:
        """
        Use Azure OpenAI chat to extract potential research questions from
        each chunk's text. Returns one string per chunk (newline-separated
        questions, or empty string if none found).
        """
        settings = get_settings()
        results: list[str] = []

        for text in texts:
            if not text or not text.strip():
                results.append("")
                continue

            truncated = text[:4000]
            try:
                response = self._openai_client.chat.completions.create(
                    model=settings.azure_openai_chat_deployment,
                    messages=[
                        {"role": "system", "content": self._QUESTION_EXTRACTION_PROMPT},
                        {"role": "user", "content": truncated},
                    ],
                    temperature=0.2,
                    max_tokens=500,
                )
                answer = response.choices[0].message.content.strip()
                if answer.upper() == "NONE":
                    results.append("")
                else:
                    results.append(answer)
            except Exception as e:
                logger.warning(f"Research question extraction failed for chunk: {e}")
                results.append("")

        return results

    # ------------------------------------------------------------------
    # Indexing pipeline
    # ------------------------------------------------------------------

    def _generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a batch of texts via Azure OpenAI."""
        response = self._openai_client.embeddings.create(
            input=texts,
            model=self._embedding_deployment,
        )
        return [item.embedding for item in response.data]

    def chunk_and_index(self, session_id: str, data: dict) -> int:
        """Two-tier indexing pipeline.

        1. Build fine-grained Tier 1 sub-chunks from the HubSpot JSON.
        2. Enrich, classify, extract questions, and embed Tier 1 chunks.
        3. Build Tier 2 section-aggregate chunks from classified Tier 1.
        4. Enrich and embed Tier 2 aggregates.
        5. Push everything to the search index in a single upload.
        """
        self.ensure_index()

        # --- Tier 1 ---
        tier1 = self._build_chunks(session_id, data)
        if not tier1:
            return 0

        tier1 = self._enrich_and_embed(tier1, session_id, tier_label="Tier 1")

        # --- Tier 2 (needs section_tags from Tier 1) ---
        tier2 = self._build_section_aggregates(session_id, tier1)
        if tier2:
            tier2 = self._enrich_and_embed(
                tier2, session_id, tier_label="Tier 2", classify_tags=False,
            )
            for agg in tier2:
                tag = agg["chunk_id"].split("_agg_")[-1]
                agg["section_tags"] = [tag]

        all_docs = tier1 + tier2
        self._search_client.upload_documents(all_docs)
        logger.info(
            f"Indexed {len(tier1)} Tier-1 + {len(tier2)} Tier-2 chunks "
            f"({len(all_docs)} total) for session {session_id}"
        )
        return len(all_docs)

    def _enrich_and_embed(
        self,
        documents: list[dict],
        session_id: str,
        *,
        tier_label: str = "",
        classify_tags: bool = True,
    ) -> list[dict]:
        """Run enrichment, section classification, question extraction,
        and embedding on a list of chunk documents (in-place)."""
        texts = [doc["content"] for doc in documents]
        label = f" ({tier_label})" if tier_label else ""

        # Enrich via Azure AI Language
        logger.info(f"Enriching {len(texts)} chunks{label} for session {session_id}...")
        enrichments = self._enrichment.enrich_batch(texts)
        for doc, enrichment in zip(documents, enrichments):
            doc["keyphrases"] = ", ".join(enrichment["keyphrases"])
            doc["entities"] = "; ".join(
                f"{e['name']} ({e['category']})" for e in enrichment["entities"]
            )
            doc["sentiment"] = enrichment["sentiment"]
            doc["sentiment_positive"] = enrichment["sentiment_scores"]["positive"]
            doc["sentiment_neutral"] = enrichment["sentiment_scores"]["neutral"]
            doc["sentiment_negative"] = enrichment["sentiment_scores"]["negative"]

        # Section tag classification
        if classify_tags:
            logger.info(f"Classifying section tags for {len(texts)} chunks{label}...")
            all_tags = self._classify_section_tags(texts)
            for doc, tags in zip(documents, all_tags):
                doc["section_tags"] = tags
        else:
            for doc in documents:
                doc.setdefault("section_tags", [])

        # Research question extraction
        logger.info(f"Extracting research questions from {len(texts)} chunks{label}...")
        questions = self._extract_potential_questions(texts)
        for doc, q in zip(documents, questions):
            doc["potential_research_questions"] = q

        # Vector embeddings
        logger.info(f"Generating embeddings for {len(texts)} chunks{label}...")
        embeddings = self._generate_embeddings(texts)
        for doc, embedding in zip(documents, embeddings):
            doc["content_vector"] = embedding

        return documents

    # ------------------------------------------------------------------
    # Text splitting helpers
    # ------------------------------------------------------------------

    # Activities shorter than this (in chars) are kept as a single chunk.
    # Only longer content gets sub-split to stay within embedding limits.
    SPLIT_THRESHOLD = 2000

    @staticmethod
    def _split_email_body(body: str) -> list[str]:
        """Split an email body into semantic paragraphs.

        Splits on numbered list items (``1) ...``, ``1. ...``) first.
        Falls back to double-newline paragraph splitting.  Filters out
        trivially short fragments (< 20 chars).
        """
        segments = _re.split(r"\n(?=\d+[\)\.]\s)", body)
        if len(segments) <= 1:
            segments = [s.strip() for s in body.split("\n\n") if s.strip()]
        return [s for s in segments if len(s) >= 20] or [body]

    @staticmethod
    def _split_meeting_notes(notes: str) -> list[tuple[str, str]]:
        """Split meeting notes into ``(heading, content)`` pairs.

        Handles two heading styles:
          - ``Heading:\\n<content on next lines>``
          - ``Heading: <content on same line>``

        A heading is a line-start word/phrase (not a bullet) followed
        by ``:``.  Falls back to a single ("Notes", full_text) pair.
        """
        heading_re = _re.compile(
            r"^(?![\-\*\d])([A-Za-z][\w\s/\-\(\)]*?):\s*",
            _re.MULTILINE,
        )

        headings = list(heading_re.finditer(notes))
        if not headings:
            return [("Notes", notes.strip())]

        pairs: list[tuple[str, str]] = []
        for i, m in enumerate(headings):
            heading = m.group(1).strip()
            start = m.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(notes)
            body = notes[start:end].strip()
            if body:
                pairs.append((heading, body))

        return pairs if pairs else [("Notes", notes.strip())]

    # ------------------------------------------------------------------
    # Tier 1: Fine-grained structural sub-chunks
    # ------------------------------------------------------------------

    def _build_chunks(self, session_id: str, data: dict) -> list[dict]:
        """Parse HubSpot JSON into fine-grained Tier 1 sub-chunks."""
        documents: list[dict] = []

        deal = data.get("deal", {})
        company = deal.get("company", {})
        contact = deal.get("primary_contact", {})
        key_fields = deal.get("key_fields", {})
        competitors = ", ".join(key_fields.get("priority_competitors", []))
        parent_deal_id = f"{session_id}_deal"

        common_participants = (
            f"{contact.get('name', '')}; {key_fields.get('internal_owner', '')}"
        )

        # --- Deal sub-chunk 1: Identity (Client & Brand) ---
        identity_text = (
            f"Client & Brand Information\n"
            f"Company: {company.get('name', '')} ({company.get('industry', '')})\n"
            f"Primary Contact: {contact.get('name', '')} - {contact.get('title', '')}\n"
            f"Email: {contact.get('email', '')}\n"
            f"Deal Stage: {deal.get('deal_stage', '')}\n"
            f"Close Date: {deal.get('close_date', '')}\n"
            f"Priority Competitors: {competitors}\n"
            f"Region Focus: {key_fields.get('region_focus', '')}"
        )
        documents.append({
            "chunk_id": f"{session_id}_deal_identity",
            "session_id": session_id,
            "chunk_type": "deal_metadata",
            "chunk_tier": "structural",
            "parent_chunk_id": parent_deal_id,
            "source_activity_id": "",
            "paragraph_index": 0,
            "content": identity_text,
            "timestamp": deal.get("close_date", ""),
            "direction": "",
            "subject": "Deal Identity",
            "participants": common_participants,
        })

        # --- Deal sub-chunk 2: Scope (competitors, region) ---
        scope_text = (
            f"Region Focus: {key_fields.get('region_focus', '')}\n"
            f"Priority Competitors: {competitors}\n"
            f"Industry: {company.get('industry', '')}"
        )
        documents.append({
            "chunk_id": f"{session_id}_deal_scope",
            "session_id": session_id,
            "chunk_type": "deal_metadata",
            "chunk_tier": "structural",
            "parent_chunk_id": parent_deal_id,
            "source_activity_id": "",
            "paragraph_index": 1,
            "content": scope_text,
            "timestamp": deal.get("close_date", ""),
            "direction": "",
            "subject": "Deal Scope",
            "participants": common_participants,
        })

        # --- Deal sub-chunk 3: Logistics (budget, timeline, owner) ---
        logistics_text = (
            f"Budget Range: {key_fields.get('budget_range', '')}\n"
            f"Target Kickoff: {key_fields.get('target_kickoff', '')}\n"
            f"Target Delivery: {key_fields.get('target_delivery', '')}\n"
            f"Internal Owner: {key_fields.get('internal_owner', '')}"
        )
        documents.append({
            "chunk_id": f"{session_id}_deal_logistics",
            "session_id": session_id,
            "chunk_type": "deal_metadata",
            "chunk_tier": "structural",
            "parent_chunk_id": parent_deal_id,
            "source_activity_id": "",
            "paragraph_index": 2,
            "content": logistics_text,
            "timestamp": deal.get("close_date", ""),
            "direction": "",
            "subject": "Deal Logistics",
            "participants": common_participants,
        })

        # --- Email activities ---
        for activity in data.get("activities", []):
            activity_type = activity.get("type", "").upper()
            activity_id = activity.get("activity_id", uuid.uuid4().hex[:8])

            if activity_type == "EMAIL":
                from_name = activity.get("from", {}).get("name", "")
                to_names = ", ".join(
                    r.get("name", "") for r in activity.get("to", [])
                )
                cc_names = ", ".join(
                    r.get("name", "") for r in activity.get("cc", [])
                )
                participants = f"From: {from_name} | To: {to_names}"
                if cc_names:
                    participants += f" | CC: {cc_names}"

                header = (
                    f"Subject: {activity.get('subject', '')}\n"
                    f"Direction: {activity.get('direction', '')}\n"
                    f"{participants}"
                )
                parent_id = f"{session_id}_{activity_id}"

                body = activity.get("body", "")
                full_content = f"{header}\n\n{body}"

                if len(full_content) <= self.SPLIT_THRESHOLD:
                    documents.append({
                        "chunk_id": f"{parent_id}_p0",
                        "session_id": session_id,
                        "chunk_type": "email",
                        "chunk_tier": "structural",
                        "parent_chunk_id": parent_id,
                        "source_activity_id": activity_id,
                        "paragraph_index": 0,
                        "content": full_content,
                        "timestamp": activity.get("timestamp", ""),
                        "direction": activity.get("direction", ""),
                        "subject": activity.get("subject", ""),
                        "participants": participants,
                    })
                else:
                    segments = self._split_email_body(body)
                    for idx, segment in enumerate(segments):
                        content = f"{header}\n\n{segment}"
                        documents.append({
                            "chunk_id": f"{parent_id}_p{idx}",
                            "session_id": session_id,
                            "chunk_type": "email",
                            "chunk_tier": "structural",
                            "parent_chunk_id": parent_id,
                            "source_activity_id": activity_id,
                            "paragraph_index": idx,
                            "content": content,
                            "timestamp": activity.get("timestamp", ""),
                            "direction": activity.get("direction", ""),
                            "subject": activity.get("subject", ""),
                            "participants": participants,
                        })

            # --- Meeting notes ---
            elif activity_type == "MEETING_NOTES":
                meeting = activity.get("meeting", {})
                attendees = ", ".join(
                    f"{a.get('name', '')} ({a.get('role', '')})"
                    for a in meeting.get("attendees", [])
                )
                header = (
                    f"Meeting: {meeting.get('title', '')}\n"
                    f"Duration: {meeting.get('duration_minutes', '')} minutes\n"
                    f"Attendees: {attendees}"
                )
                parent_id = f"{session_id}_{activity_id}"

                notes = activity.get("notes", "")
                full_content = f"{header}\n\n{notes}"

                if len(full_content) <= self.SPLIT_THRESHOLD:
                    documents.append({
                        "chunk_id": f"{parent_id}_s0",
                        "session_id": session_id,
                        "chunk_type": "meeting_notes",
                        "chunk_tier": "structural",
                        "parent_chunk_id": parent_id,
                        "source_activity_id": activity_id,
                        "paragraph_index": 0,
                        "content": full_content,
                        "timestamp": activity.get("timestamp", ""),
                        "direction": "",
                        "subject": meeting.get("title", ""),
                        "participants": attendees,
                    })
                else:
                    sections = self._split_meeting_notes(notes)
                    for idx, (heading, body_text) in enumerate(sections):
                        content = f"{header}\n\n[{heading}]\n{body_text}"
                        documents.append({
                            "chunk_id": f"{parent_id}_s{idx}",
                            "session_id": session_id,
                            "chunk_type": "meeting_notes",
                            "chunk_tier": "structural",
                            "parent_chunk_id": parent_id,
                            "source_activity_id": activity_id,
                            "paragraph_index": idx,
                            "content": content,
                            "timestamp": activity.get("timestamp", ""),
                            "direction": "",
                            "subject": f"{meeting.get('title', '')} — {heading}",
                            "participants": attendees,
                        })

        # --- Brief requirements → additional_info chunk ---
        brief = data.get("brief_requirements", {})
        if brief:
            tone = brief.get("tone", "")
            sections_list = ", ".join(brief.get("format_sections", []))
            content = (
                f"The client has specified a preferred tone of \"{tone}\" for all "
                f"deliverables. Their expected output structure includes: {sections_list}."
            )
            documents.append({
                "chunk_id": f"{session_id}_brief_requirements",
                "session_id": session_id,
                "chunk_type": "brief_requirements",
                "chunk_tier": "structural",
                "parent_chunk_id": "",
                "source_activity_id": "",
                "paragraph_index": 0,
                "content": content,
                "timestamp": "",
                "direction": "",
                "subject": "Client Brief Requirements",
                "participants": "",
            })

        return documents

    # ------------------------------------------------------------------
    # Tier 2: Section aggregate chunks
    # ------------------------------------------------------------------

    def _build_section_aggregates(
        self,
        session_id: str,
        tier1_chunks: list[dict],
    ) -> list[dict]:
        """Assemble one aggregate chunk per template section.

        Groups all Tier 1 sub-chunks by their ``section_tags`` and
        concatenates the content, producing a single de-duplicated
        document per section that agents can retrieve directly.
        """
        section_texts: dict[str, list[str]] = defaultdict(list)
        seen: dict[str, set[str]] = defaultdict(set)

        for chunk in tier1_chunks:
            for tag in chunk.get("section_tags", []):
                cid = chunk["chunk_id"]
                if cid not in seen[tag]:
                    seen[tag].add(cid)
                    section_texts[tag].append(chunk["content"])

        aggregates: list[dict] = []
        for tag, texts in section_texts.items():
            merged = "\n\n---\n\n".join(texts)
            aggregates.append({
                "chunk_id": f"{session_id}_agg_{tag}",
                "session_id": session_id,
                "chunk_type": "section_aggregate",
                "chunk_tier": "section_aggregate",
                "parent_chunk_id": "",
                "source_activity_id": "",
                "paragraph_index": 0,
                "content": merged,
                "timestamp": "",
                "direction": "",
                "subject": f"Section Aggregate: {tag}",
                "participants": "",
            })

        return aggregates

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    _DEFAULT_SELECT = [
        "chunk_id", "chunk_type", "chunk_tier", "content", "timestamp",
        "direction", "subject", "participants",
        "parent_chunk_id", "source_activity_id", "paragraph_index",
        "keyphrases", "entities", "sentiment",
        "potential_research_questions", "section_tags",
    ]

    def search(
        self,
        session_id: str,
        query: str,
        top: int = 10,
        chunk_type: str | None = None,
        section_tag: str | None = None,
        chunk_tier: str | None = None,
    ) -> list[dict]:
        """Search indexed documents scoped to a specific session."""
        filter_expr = f"session_id eq '{session_id}'"
        if chunk_type:
            filter_expr += f" and chunk_type eq '{chunk_type}'"
        if section_tag:
            filter_expr += f" and section_tags/any(t: t eq '{section_tag}')"
        if chunk_tier:
            filter_expr += f" and chunk_tier eq '{chunk_tier}'"

        results = self._search_client.search(
            search_text=query,
            filter=filter_expr,
            top=top,
            select=self._DEFAULT_SELECT,
        )
        return [dict(r) for r in results]

    def search_by_section(
        self,
        session_id: str,
        section_tag: str,
        query: str = "*",
        top: int = 10,
        prefer_aggregates: bool = True,
    ) -> list[dict]:
        """Retrieve chunks tagged for a specific brief section.

        When *prefer_aggregates* is True the method first tries to
        return the Tier-2 section-aggregate chunk.  If none exists it
        falls back to Tier-1 structural sub-chunks.
        """
        if prefer_aggregates:
            agg_filter = (
                f"session_id eq '{session_id}' "
                f"and chunk_tier eq 'section_aggregate' "
                f"and section_tags/any(t: t eq '{section_tag}')"
            )
            agg_results = list(self._search_client.search(
                search_text=query,
                filter=agg_filter,
                top=1,
                select=self._DEFAULT_SELECT,
            ))
            if agg_results:
                return [dict(r) for r in agg_results]

        filter_expr = (
            f"session_id eq '{session_id}' "
            f"and section_tags/any(t: t eq '{section_tag}')"
        )
        results = self._search_client.search(
            search_text=query,
            filter=filter_expr,
            top=top,
            select=self._DEFAULT_SELECT,
        )
        return [dict(r) for r in results]

    def get_all_chunks(self, session_id: str) -> list[dict]:
        """Retrieve all chunks for a session (both tiers)."""
        results = self._search_client.search(
            search_text="*",
            filter=f"session_id eq '{session_id}'",
            top=100,
            select=self._DEFAULT_SELECT,
        )
        return [dict(r) for r in results]

    def delete_session_chunks(self, session_id: str):
        """Delete all chunks for a session (both tiers)."""
        chunks = self.get_all_chunks(session_id)
        if chunks:
            keys = [{"chunk_id": c["chunk_id"]} for c in chunks]
            self._search_client.delete_documents(keys)
