"""
Executive Brief polishing agent backed by Azure AI Foundry.

This agent does NOT use AzureAISearchTool — it receives all pre-generated
section outputs as context and produces a single polished, leadership-ready
Executive Research Brief.  It is designed to run on a higher-tier model
(configurable via AZURE_AI_POLISH_MODEL_DEPLOYMENT) after the individual
section agents have completed their RAG-backed generation.
"""

import logging
import re
import time
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MessageTextContent, RunStatus
from azure.identity import DefaultAzureCredential
from app.config import get_settings
from app.agents.base_agent import _is_rate_limited, MAX_RETRIES, RETRY_WAIT_SECONDS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Senior Strategic Consultant and Research Lead. Your goal is to \
transform a raw, section-by-section draft into a polished, leadership-ready \
Executive Research Brief.

=== CORE DIRECTIVES ===

TONE: Professional, objective, authoritative. No "fluff," no corporate \
jargon, no filler phrases like "it is important to note" or "as previously \
mentioned."

ZERO HALLUCINATION: You may ONLY use facts, names, dates, numbers, and \
details that appear in the raw draft provided to you. If a piece of \
information is not in the input, do NOT add it. When in doubt, leave it out.

STRICT DE-DUPLICATION: This is your most important task. Each fact, date, \
competitor name, channel, or detail must appear in EXACTLY ONE section — \
the section where it is most relevant. Apply these ownership rules:
- Launch date, product name, event context → PROJECT_OVERVIEW only.
- Analysis window, lookback period → DATA_TIMEFRAME only (keep it to 1-3 \
  bullets max).
- Competitor names as a list → CLIENT_BRAND (scope definition).
- What we want to learn about competitors → OBJECTIVES or RESEARCH_QUESTIONS.
- Milestone dates, deadlines → TIMELINE only.
- Budget, geographic limits, tool constraints → KEY_ASSUMPTIONS only.
- Deliverable formats, slide counts → DELIVERABLES only.
If a detail already lives in its owning section, DELETE it from every other \
section — even if the raw draft repeats it.

CONCISENESS: Prefer bullets over paragraphs. Remove any sentence that does \
not add new information the reader hasn't already seen in the document.

FORMATTING: Use **bold** for key names, dates, and targets. Use ### for \
sub-headings within a section. Use tables (Markdown pipe syntax) for \
stakeholder lists and timelines.

=== REQUIRED OUTPUT STRUCTURE ===

Return the polished document with each section wrapped in its tag. Only \
include a tag if the section has meaningful content.

[METADATA]
Return ONLY a valid JSON object (no markdown fences) with these keys: \
project_name, client, client_contact, additional_stakeholders, version, \
hours_allocation, prepared_by. Preserve original values — only fix \
formatting and consistency.

[CLIENT_BRAND]
Company, brand, industry, region, key contacts. List primary and secondary \
competitors here as scope definition.

[PROJECT_OVERVIEW]
One concise paragraph: what is being done, why, and the key event/launch \
driving it. Mention the launch date ONCE here. Do not list competitors, \
channels, or deliverables — those belong in their own sections.

[OBJECTIVES]
Bulleted goals grouped by category (Competitive, Content, Media, Strategic). \
Each bullet is a discrete, measurable goal. Do not restate the project \
background.

[RESEARCH_QUESTIONS]
Questions grouped by category (Paid Search, Social/Video, Paid Media, \
Messaging, Strategic). No preamble — just the grouped questions.

[DATA_TIMEFRAME]
ONLY the primary analysis window — 1 to 3 bullets maximum. Do NOT repeat \
launch dates, competitor names, or channel lists here.

[RESEARCH_USAGE]
How the research will be used and by whom. Do not re-list deliverables or \
timeline dates.

[DELIVERABLES]
What will be delivered (formats, page/slide counts, content). Do not repeat \
deadlines — those go in TIMELINE.

[TIMELINE]
A Markdown table of milestones and dates. Do not add narrative — just the \
table.

[KEY_ASSUMPTIONS]
Budget, geographic focus, channel prioritization, methodology constraints. \
State each once as a bullet.

[ADDITIONAL_INFO]
Only if there is genuinely new context not captured above. Otherwise omit \
this tag entirely.

=== FINAL CHECKLIST (apply before returning) ===
1. Scan every section — if a date, name, or fact appears in more than one \
   section, delete it from the less-relevant one.
2. Verify [DATA_TIMEFRAME] contains ONLY the analysis window (no launch \
   dates, no competitor names, no channel lists).
3. Verify [TIMELINE] is a table, not prose.
4. Verify [METADATA] is valid JSON with string values only.
5. Verify you have not invented any information not present in the input.
"""

# Maps output tags → the section names used by the rest of the pipeline
SECTION_TAGS = [
    "METADATA",
    "CLIENT_BRAND",
    "PROJECT_OVERVIEW",
    "OBJECTIVES",
    "RESEARCH_QUESTIONS",
    "DATA_TIMEFRAME",
    "RESEARCH_USAGE",
    "DELIVERABLES",
    "TIMELINE",
    "KEY_ASSUMPTIONS",
    "ADDITIONAL_INFO",
]


class ExecutiveBriefAgent:
    """Polishing agent that unifies all section outputs into a cohesive brief."""

    def __init__(self):
        settings = get_settings()
        self._client = AIProjectClient.from_connection_string(
            credential=DefaultAzureCredential(),
            conn_str=settings.azure_ai_project_connection_string,
        )
        self._model = settings.azure_ai_polish_model_deployment
        self._agent_id: str | None = None

    def _ensure_agent(self):
        if self._agent_id:
            return
        agent = self._client.agents.create_agent(
            model=self._model,
            name="ExecutiveBriefAgent",
            instructions=SYSTEM_PROMPT,
        )
        self._agent_id = agent.id

    def polish(self, sections: dict[str, str]) -> dict[str, str]:
        """
        Accept a dict of {section_name: raw_content} from the individual
        agents, send the combined draft to the polishing model, and return
        a dict of {section_tag: polished_content}.

        Retries up to MAX_RETRIES times on rate-limit (429) errors, waiting
        RETRY_WAIT_SECONDS between attempts.
        """
        self._ensure_agent()
        user_prompt = self._build_prompt(sections)

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                thread = self._client.agents.create_thread()
                self._client.agents.create_message(
                    thread_id=thread.id,
                    role="user",
                    content=user_prompt,
                )
                run = self._client.agents.create_run(
                    thread_id=thread.id,
                    agent_id=self._agent_id,
                )
            except Exception as exc:
                if _is_rate_limited(exc) and attempt < MAX_RETRIES:
                    logger.warning(
                        "Rate-limited on ExecutiveBriefAgent (attempt %d/%d), waiting %ds …",
                        attempt, MAX_RETRIES, RETRY_WAIT_SECONDS,
                    )
                    time.sleep(RETRY_WAIT_SECONDS)
                    continue
                raise

            run = self._poll_run(thread.id, run.id)

            if run.status == RunStatus.COMPLETED:
                raw_response = self._extract_response(thread.id)
                return self._parse_tagged_output(raw_response)

            error_msg = run.last_error.message if run.last_error else str(run.status)
            if _is_rate_limited(error_msg) and attempt < MAX_RETRIES:
                logger.warning(
                    "Rate-limited run on ExecutiveBriefAgent (attempt %d/%d): %s — waiting %ds …",
                    attempt, MAX_RETRIES, error_msg, RETRY_WAIT_SECONDS,
                )
                time.sleep(RETRY_WAIT_SECONDS)
                last_error = error_msg
                continue

            raise RuntimeError(
                f"Executive brief agent run failed with status '{run.status}': {error_msg}"
            )

        raise RuntimeError(
            f"ExecutiveBriefAgent exhausted {MAX_RETRIES} retries "
            f"(last error: {last_error})"
        )

    def cleanup(self):
        if self._agent_id:
            try:
                self._client.agents.delete_agent(self._agent_id)
            except Exception:
                pass
            self._agent_id = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(sections: dict[str, str]) -> str:
        lines = [
            "Below is a raw draft of an Executive Research Brief, produced "
            "section-by-section by specialist agents. Each section is labeled "
            "with its tag.\n",
            "Your task: polish, de-duplicate, and restructure this into a "
            "single cohesive, leadership-ready document. Follow your system "
            "instructions for structure, tone, and output format.\n",
            "--- RAW DRAFT START ---\n",
        ]
        for tag, content in sections.items():
            if content and content.strip():
                lines.append(f"[{tag.upper()}]")
                lines.append(content.strip())
                lines.append("")
        lines.append("--- RAW DRAFT END ---")
        return "\n".join(lines)

    @staticmethod
    def _parse_tagged_output(raw: str) -> dict[str, str]:
        """Parse [TAG]…[NEXT_TAG] blocks from the agent response."""
        result: dict[str, str] = {}
        for i, tag in enumerate(SECTION_TAGS):
            pattern = rf"\[{tag}\]\s*\n(.*?)(?=\n\[(?:{'|'.join(SECTION_TAGS)})\]|$)"
            match = re.search(pattern, raw, re.DOTALL)
            if match:
                content = match.group(1).strip()
                if content:
                    result[tag] = content
        return result

    def _extract_response(self, thread_id: str) -> str:
        messages = self._client.agents.list_messages(thread_id=thread_id)
        for msg in messages.data:
            if msg.role == "assistant":
                parts = []
                for block in msg.content:
                    if isinstance(block, MessageTextContent):
                        parts.append(block.text.value)
                return "\n".join(parts).strip()
        return ""

    def _poll_run(self, thread_id: str, run_id: str, timeout: int = 180):
        """Poll with a longer timeout — polishing a full document takes longer."""
        terminal = {
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.EXPIRED,
        }
        start = time.time()
        while time.time() - start < timeout:
            run = self._client.agents.get_run(
                thread_id=thread_id, run_id=run_id
            )
            if run.status in terminal:
                return run
            time.sleep(2)
        raise TimeoutError(
            f"Executive brief agent did not complete within {timeout}s"
        )
