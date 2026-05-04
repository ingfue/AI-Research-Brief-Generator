# AI Research Brief Generator

**Repository:** [github.com/ingfue/AI-Research-Brief-Generator](https://github.com/ingfue/AI-Research-Brief-Generator)

```bash
git clone https://github.com/ingfue/AI-Research-Brief-Generator.git
```

Transform HubSpot deal exports (JSON) and conversation history into a **professional research-brief Word document**. A **FastAPI** backend chunks and indexes data into **Azure AI Search**, then runs **Azure AI Foundry** agents (native RAG per upload session). A **React / Vite** frontend supports full-document generation or a step-by-step human review workflow.

---

## GitHub repository

| | |
| --- | --- |
| **URL** | [https://github.com/ingfue/AI-Research-Brief-Generator](https://github.com/ingfue/AI-Research-Brief-Generator) |
| **Clone (HTTPS)** | `https://github.com/ingfue/AI-Research-Brief-Generator.git` |
| **Suggested description** | HubSpot deal JSON → AI-generated research brief (.docx) using Azure AI Foundry agents, Azure AI Search RAG, FastAPI, and React — with PowerShell + Azure CLI infrastructure automation. |

---

## Infrastructure as Code (Azure)

Cloud resources are provisioned through **scripts and the Azure CLI**, not ad-hoc portal-only setup, so environments stay **reproducible** and **reviewable** in Git.

| Artifact | Role |
| --- | --- |
| [`infra/setup-azure.ps1`](infra/setup-azure.ps1) | **Main IaC entrypoint**: creates storage (blob containers for uploads + generated docs), **Azure AI Search**, **Azure OpenAI** (chat + embedding deployments), **Azure AI Language** (enrichment), **Azure AI Foundry** hub + project, and **workspace connections** (OpenAI + AI Search) so agents perform **native RAG**. Optionally writes `backend/.env` with connection strings and keys. |
| [`infra/teardown-azure.ps1`](infra/teardown-azure.ps1) | Removes resources created by the setup script (defaults assume a dedicated resource group; the RG itself is not deleted unless you handle it separately). |
| [`infra/README.md`](infra/README.md) | **Manual IaC path**: same resources using explicit `az` / `az ml` commands—useful for learning, debugging, or CI-style runs without PowerShell. |

**Style of IaC:** imperative automation via **PowerShell** and **`az` CLI** (including `az ml` for Foundry). This repo does **not** ship Bicep, ARM, or Terraform; trade-off is **lowest barrier** (CLI only) vs **declarative state files**. Defaults in the scripts use neutral names like `rg-proposal-poc`; you must pick **globally unique** names for storage, search, and OpenAI accounts.

**Secrets:** keep configuration in `backend/.env` (created locally). See [`backend/.env.example`](backend/.env.example). **Do not commit `.env`.**

---

## Table of contents

- [GitHub repository](#github-repository)
- [Infrastructure as Code (Azure)](#infrastructure-as-code-azure)
- [High-level architecture](#high-level-architecture)
- [Data ingestion (two-tier chunking)](#data-ingestion-pipeline-two-tier-chunking-strategy)
- [Agent architecture](#agent-architecture)
- [End-to-end workflows](#end-to-end-agent-workflow)
- [Project structure](#project-structure)
- [Quick start](#quick-start)
- [API summary](#api-endpoints)
- [Tech stack](#tech-stack)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    USER (Browser)                                   │
│                                  localhost:5173                                     │
└──────────────────────────────────────┬──────────────────────────────────────────────┘
                                       │  HTTP (Vite proxy /api → :8000)
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND — React / Vite / TypeScript                       │
│                                                                                      │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────────┐  ┌───────────────────────┐  │
│  │  HomePage  │  │  UploadPage  │  │  FullGeneratePage │  │   HumanReviewPage     │  │
│  └────────────┘  └──────────────┘  └───────────────────┘  └───────────────────────┘  │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │ SessionSelector  │  │SectionStepper│  │SectionEditor │  │    ToneAdjuster     │   │
│  └──────────────────┘  └──────────────┘  └──────────────┘  └─────────────────────┘   │
│                                  src/services/api.ts (Axios)                         │
└──────────────────────────────────────┬───────────────────────────────────────────────┘
                                       │  REST API
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                            BACKEND — Python / FastAPI                                │
│                                                                                      │
│  ┌──────────────────────────── Routers ───────────────────────────────────────────┐  │
│  │  /api/upload    /api/sessions    /api/generate/*    /api/documents/*  /api/tone│  │
│  └────────┬───────────┬──────────────────┬───────────────────┬──────────────┬─────┘  │
│           │           │                  │                   │              │        │
│  ┌────────▼───┐ ┌─────▼─────┐  ┌────────▼──────────┐ ┌─────▼──────┐ ┌────▼──────┐    │
│  │   Blob     │ │  Search   │  │ AgentOrchestrator │ │  Document  │ │   Tone    │    │
│  │  Service   │ │  Service  │  │                   │ │  Builder   │ │  Service  │    │
│  └─────┬──────┘ └─────┬─────┘  └────────┬──────────┘ └─────┬──────┘ └────┬──────┘    │
│        │              │                 │                    │              │        │
│        │              │        ┌─────────▼──────────┐        │              │        │
│        │              │        │  11 Foundry Agents │        │              │        │
│        │              │        │  (BaseAgent subs)  │        │              │        │
│        │              │        └─────────┬──────────┘        │              │        │
└────────┼──────────────┼─────────────────┼────────────────────┼──────────────┼────────┘
         │              │                 │                    │              │
         ▼              ▼                 ▼                    ▼              ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                               AZURE CLOUD SERVICES                                   │
│                                                                                      │
│  ┌──────────────┐  ┌───────────────────┐  ┌───────────────────────────────────────┐  │
│  │ Blob Storage │  │   AI Search       │  │         Azure AI Foundry              │  │
│  │              │  │   (RAG Index)     │  │                                       │  │
│  │ hubspot-     │  │ proposal-chunks   │  │  ┌──────────┐  ┌──────────────────┐   │  │
│  │  uploads/    │  │  • Tier 1 chunks  │  │  │  Agents  │  │  Azure OpenAI    │   │  │
│  │ generated-   │  │  • Tier 2 aggs    │  │  │  (live)  │  │  (gpt-4o / emb)  │   │  │
│  │  docs/       │  │  • Vector + Text  │  │  └──────────┘  └──────────────────┘   │  │
│  └──────────────┘  └───────────────────┘  └───────────────────────────────────────┘  │
│                                                                                      │
│  ┌───────────────────┐                                                               │
│  │ Azure AI Language │                                                               │
│  │ (Text Analytics)  │                                                               │
│  └───────────────────┘                                                               │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Ingestion Pipeline (Two-Tier Chunking Strategy)

The ingestion system converts raw HubSpot JSON into a richly indexed search corpus that agents can query. It uses a **two-tier chunking architecture** to give agents both granular detail and pre-assembled section views.

```
┌──────────────────────────────────────────────────────────────────────┐
│                    HubSpot Deal JSON (uploaded file)                 │
│                                                                      │
│  {                                                                   │
│    "deal": { company, contact, key_fields, stage, dates... },        │
│    "activities": [                                                   │
│      { type: "EMAIL", from, to, cc, body, subject... },              │
│      { type: "MEETING_NOTES", meeting, notes, attendees... }         │
│    ],                                                                │
│    "brief_requirements": { tone, format_sections }                   │
│  }                                                                   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                        POST /api/upload
                                   │
                    ┌──────────────┼──────────────┐
                    ▼                             ▼
          ┌─────────────────┐          ┌────────────────────────────────────────────┐
          │   Blob Storage   │         │         SearchService.chunk_and_index()    │
          │                  │         │                                            │
          │  {session_id}    │         │  ┌──────────────────────────────────────┐  │
          │    .json         │         │  │      TIER 1: Structural Chunks       │  │
          └─────────────────┘          │  │                                      │  │
                                       │  │  Deal JSON ──► 3 sub-chunks:         │  │
                                       │  │    • Identity (client, brand, contact)│ │
                                       │  │    • Scope (competitors, region)     │  │
                                       │  │    • Logistics (budget, timeline)    │  │
                                       │  │                                      │  │
                                       │  │  Emails ──► split by paragraph/list  │  │
                                       │  │    (< 2000 chars → single chunk)     │  │
                                       │  │    (> 2000 chars → paragraph split)  │  │
                                       │  │                                      │  │
                                       │  │  Meeting Notes ──► split by heading  │  │
                                       │  │    "Heading:\n content" pairs        │  │
                                       │  │    (< 2000 chars → single chunk)     │  │
                                       │  │                                      │  │
                                       │  │  Brief Requirements ──► 1 chunk      │  │
                                       │  │    (tone + format preferences)       │  │
                                       │  └──────────────────┬───────────────────┘  │
                                       │                     │                      │
                                       │                     ▼                      │
                                       │  ┌──────────────────────────────────────┐  │
                                       │  │    ENRICHMENT PIPELINE (per chunk)   │  │
                                       │  │                                      │  │
                                       │  │  1. Azure AI Language                │  │
                                       │  │     • Key phrase extraction          │  │
                                       │  │     • Named entity recognition       │  │
                                       │  │     • Sentiment analysis (scores)    │  │
                                       │  │                                      │  │
                                       │  │  2. Azure OpenAI (Chat)              │  │
                                       │  │     • Section tag classification     │  │
                                       │  │       (multi-label: which brief      │  │
                                       │  │        sections is this relevant to?)│  │
                                       │  │     • Research question extraction   │  │
                                       │  │       (explicit + implicit questions)│  │
                                       │  │                                      │  │
                                       │  │  3. Azure OpenAI (Embeddings)        │  │
                                       │  │     • 1536-dim vector per chunk      │  │
                                       │  └──────────────────┬───────────────────┘  │
                                       │                     │                      │
                                       │                     ▼                      │
                                       │  ┌──────────────────────────────────────┐  │
                                       │  │     TIER 2: Section Aggregates       │  │
                                       │  │                                      │  │
                                       │  │  Group Tier 1 chunks by section_tag  │  │
                                       │  │                                      │  │
                                       │  │  For each section tag:               │  │
                                       │  │    Merge all Tier 1 text → single    │  │
                                       │  │    "section_aggregate" chunk         │  │
                                       │  │                                      │  │
                                       │  │  Result: ~11 aggregate chunks        │  │
                                       │  │    (one per brief section)           │  │
                                       │  │                                      │  │
                                       │  │  Re-enrich + re-embed aggregates     │  │
                                       │  │  (skip tag classification — tag is   │  │
                                       │  │   already known from grouping)       │  │
                                       │  └──────────────────┬───────────────────┘  │
                                       │                     │                      │
                                       │                     ▼                      │
                                       │  ┌──────────────────────────────────────┐  │
                                       │  │     UPLOAD TO AZURE AI SEARCH        │  │
                                       │  │                                      │  │
                                       │  │  All Tier 1 + Tier 2 documents       │  │
                                       │  │  in a single batch upload            │  │
                                       │  │                                      │  │
                                       │  │  Index fields per document:          │  │
                                       │  │    • chunk_id (key)                  │  │
                                       │  │    • session_id (filterable)         │  │
                                       │  │    • chunk_tier (structural / agg)   │  │
                                       │  │    • content (searchable)            │  │
                                       │  │    • content_vector (1536-dim)       │  │
                                       │  │    • section_tags[] (filterable)     │  │
                                       │  │    • keyphrases, entities, sentiment │  │
                                       │  │    • potential_research_questions    │  │
                                       │  │    • chunk_type, timestamp, etc.     │  │
                                       │  └──────────────────────────────────────┘  │
                                       └────────────────────────────────────────────┘
```

### Why Two Tiers?


| Tier       | Type                | Purpose                                                                                                                                                                            |
| ---------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Tier 1** | `structural`        | Fine-grained sub-chunks (individual email paragraphs, meeting note headings, deal field groups). Preserves original structure for granular detail retrieval.                       |
| **Tier 2** | `section_aggregate` | One pre-assembled chunk per brief section combining all Tier 1 text classified for that section. Gives agents a clean, de-duplicated view of everything relevant to their section. |


Agents are instructed to **search for Tier 2 aggregates first** (fast, comprehensive) and **fall back to Tier 1 sub-chunks** when they need more specific detail.

### Section Tag Classification

During indexing, each chunk is classified by an LLM into one or more of 11 section tags. A single chunk can receive **multiple tags** (e.g., an email about competitor scope gets both `project_overview` and `research_questions`). The valid tags are:

```
client_brand  |  project_overview  |  objectives  |  research_questions
data_timeframe  |  research_usage  |  deliverables  |  timeline
key_assumptions  |  additional_info  |  metadata
```

---

## Agent Architecture

### Agent System Overview

Each section of the research brief is generated by a **dedicated AI Foundry agent** — a real server-side resource in Azure AI Foundry with its own system prompt and search tool.

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                          AgentOrchestrator                                     │
│                                                                                │
│  Manages agent lifecycle: create → run → cache → cleanup                       │
│  Iterates SectionName enum in definition order                                 │
│  Caches raw output per agent class to avoid duplicate Foundry calls            │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                        SECTION_AGENT_MAP                                 │  │
│  │                                                                          │  │
│  │  SectionName           Agent Class              Output Tag               │  │
│  │  ─────────────────     ─────────────────────    ──────────────────       │  │
│  │  metadata              MetadataAgent            (JSON → MetadataFields)  │  │
│  │  client_brand          ClientBrandAgent         [CLIENT_BRAND]           │  │
│  │  project_overview      ProjectOverviewAgent     [PROJECT_OVERVIEW]       │  │
│  │  objectives            ObjectivesAgent          [OBJECTIVES]             │  │
│  │  research_questions    ResearchQuestionsAgent   [RESEARCH_QUESTIONS]     │  │
│  │  data_timeframe        DataTimeframeAgent       [DATA_TIMEFRAME]         │  │
│  │  research_usage        ResearchUsageAgent       [RESEARCH_USAGE]         │  │
│  │  deliverables          DeliverablesAgent        [DELIVERABLES]           │  │
│  │  timeline              TimelineAgent            [TIMELINE]               │  │
│  │  key_assumptions       KeyAssumptionsAgent      [KEY_ASSUMPTIONS]        │  │
│  │  additional_info       AdditionalAgent          [ADDITIONAL_INFO]        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  + ToneAgent (standalone, no search tool — rewrites content by style preset)   │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Agent Lifecycle (per session)

```
  generate_section(session_id, section_name)
         │
         ▼
  ┌─────────────────┐     Already       ┌───────────────────┐
  │ Check agent     │  ──── exists? ──► │ Reuse cached      │
  │ cache for session│      Yes         │ agent instance    │
  └────────┬────────┘                   └─────────┬─────────┘
           │ No                                    │
           ▼                                       │
  ┌─────────────────────────────────────────┐      │
  │ Create Foundry Agent                    │      │
  │                                         │      │
  │  • System prompt from SYSTEM_PROMPT     │      │
  │  • AzureAISearchTool attached:          │      │
  │    ─ index: proposal-chunks             │      │
  │    ─ filter: session_id eq '{id}'       │      │
  │    ─ query_type: SIMPLE                 │      │
  │    ─ top_k: 3                           │      │
  │  • Agent name: {ClassName}_{session_id} │      │
  └────────────────┬────────────────────────┘      │
                   │                               │
                   ▼                               ▼
  ┌─────────────────────────────────────────────────────────┐
  │ Check output cache                                      │
  │  (same agent class may serve its tag from cached output)│
  └────────────────────┬────────────────────────────────────┘
                       │ Cache miss
                       ▼
  ┌─────────────────────────────────────────────────────────┐
  │ Execute Agent Run                                       │
  │                                                         │
  │  1. Create Thread                                       │
  │  2. Post user message (search strategy + instructions)  │
  │  3. Create Run (agent executes, queries AI Search)      │
  │  4. Poll until terminal status (1s interval, 120s max)  │
  │  5. Extract last assistant message from thread          │
  │  6. Clean output (strip citations, markdown, bullets)   │
  └────────────────────┬────────────────────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────────────────┐
  │ Parse Tagged Output                                     │
  │                                                         │
  │  Agent output contains [TAG] markers.                   │
  │  Extract content between [SECTION_TAG] delimiters.      │
  │  Return as SectionContent with status = "review"        │
  └────────────────────┬────────────────────────────────────┘
                       │
                       ▼
               SectionContent { section, content, status }
```

### How Agents Query the Index (Native RAG)

Each agent has an `AzureAISearchTool` baked into its Foundry definition. When an agent runs, the Foundry runtime **natively executes search queries** on behalf of the agent — the agent decides what to search for based on its system prompt and the user message.

```
┌──────────────────┐         ┌───────────────────────┐         ┌─────────────────┐
│  Foundry Agent   │  ──►    │  AzureAISearchTool    │  ──►    │  AI Search      │
│                  │         │                       │         │  Index          │
│  "Find data      │         │  filter:              │         │                 │
│   about project  │         │    session_id eq 'x'  │         │  Returns top 3  │
│   timeline"      │         │  query_type: SIMPLE   │         │  matching chunks│
│                  │  ◄──    │  top_k: 3             │  ◄──    │  (Tier 1 or 2)  │
│                  │         │                       │         │                 │
│  Synthesizes     │         └───────────────────────┘         └─────────────────┘
│  section content │
│  from results    │    Session isolation: each agent can ONLY
└──────────────────┘    see chunks from its own session_id
```

### Individual Agent Responsibilities


| Agent                      | Section            | What It Produces                                                                                                                                                                        |
| -------------------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **MetadataAgent**          | Header fields      | Structured JSON: project title, client name, contact, internal owner, date, deal stage                                                                                                  |
| **ClientBrandAgent**       | Client & Brand     | One sentence: parent company, brand, product category                                                                                                                                   |
| **ProjectOverviewAgent**   | Project Overview   | 2-3 sentences: research purpose, strategic decision, full competitor scope                                                                                                              |
| **ObjectivesAgent**        | Objectives         | Checkbox-style objectives organized by category                                                                                                                                         |
| **ResearchQuestionsAgent** | Research Questions | Numbered research questions (uses `potential_research_questions` from index)                                                                                                            |
| **DataTimeframeAgent**     | Data Timeframe     | Definitive timeframe statement (no hedging language)                                                                                                                                    |
| **ResearchUsageAgent**     | Research Usage     | Who uses outputs, for what decisions                                                                                                                                                    |
| **DeliverablesAgent**      | Deliverables       | Output formats, scope, named sections                                                                                                                                                   |
| **TimelineAgent**          | Timeline           | Dates, milestones, OOO periods if relevant                                                                                                                                              |
| **KeyAssumptionsAgent**    | Key Assumptions    | Scope boundaries, constraints, revision expectations                                                                                                                                    |
| **AdditionalAgent**        | Additional Info    | Links, docs, tone preferences, stakeholder context                                                                                                                                      |
| **ToneAgent**              | *(any section)*    | Rewrites existing content with a chosen style preset (professional, concise, persuasive, leadership-ready, friendly). Has **no search tool** — operates purely on the text given to it. |


---

## End-to-End Agent Workflow

When a user clicks "Generate Full Document", here is exactly what happens, agent by agent, in order:

### Step 0: Upload & Indexing (before any agent runs)

The user uploads a HubSpot JSON file. `SearchService` chunks it into Tier 1 sub-chunks (deal fields, email paragraphs, meeting note headings), enriches each chunk (key phrases, entities, sentiment, section tags, research question extraction, vector embeddings), then builds Tier 2 section aggregates — one merged chunk per brief section. Everything is pushed to Azure AI Search, scoped by `session_id`.

### Step 1: MetadataAgent

Searches the index for deal identity chunks (company name, contact info, deal stage, budget, internal owner). Returns a **structured JSON object** with fields like `project_name`, `client`, `client_contact`, `additional_stakeholders`, `version`, `hours_allocation`, and `prepared_by`. This JSON populates the header table of the final Word document.

### Step 2: ClientBrandAgent

Searches for chunks tagged `client_brand`. Produces bullet points identifying the parent company, brand name, product line, industry, region, primary contact, and any additional stakeholders. For the Earth's Own deal, this would output things like "Parent Company: Earth's Own", "Industry: CPG / Beverage", "Region: Canada".

### Step 3: ProjectOverviewAgent

Searches for chunks tagged `project_overview`. Writes 2-3 sentences describing the research purpose, the strategic context driving it (e.g. an upcoming product launch), and the full competitor scope (must-have vs nice-to-have). This is the "what and why" of the project.

### Step 4: ObjectivesAgent

Searches for chunks tagged `objectives`. Produces checkbox-style objectives organized by category (Competitive Intelligence, Content & Creative, Media & Spend, Strategic). Each objective is a discrete goal the research should achieve.

### Step 5: ResearchQuestionsAgent

Searches for chunks tagged `research_questions` AND `additional_info` (to catch leadership priorities from stakeholder emails). Also pulls from the `potential_research_questions` field that was pre-extracted during indexing. Produces categorized research questions grouped into: Paid Search & SEM, Social & Video, Paid Media & Spend, Messaging & Creative, and Strategic & Competitive Landscape. These questions define what the research deliverable will answer.

### Step 6: DataTimeframeAgent

Searches for chunks tagged `data_timeframe`. Produces a definitive statement about the analysis window (e.g. "Last 12 months, with 6 months as a minimum"). No hedging language — just the timeframe.

### Step 7: ResearchUsageAgent

Searches for chunks tagged `research_usage`. Identifies who will use the research outputs, what decisions it will inform, and the audience (e.g. "Leadership team — to inform channel allocation and messaging strategy for the May oat milk launch").

### Step 8: DeliverablesAgent

Searches for chunks tagged `deliverables`. Lists the expected output formats (slide deck, one-page brief), specific content requests (e.g. "include a section called Recommended Moves for Earth's Own with 5 bullets"), slide counts, and structural requirements.

### Step 9: TimelineAgent

Searches for chunks tagged `timeline`. Produces a milestone table with dates (kickoff, delivery, any OOO periods). Pulls from deal logistics, email discussions, and meeting notes.

### Step 10: KeyAssumptionsAgent

Searches for chunks tagged `key_assumptions`. Lists scope boundaries, constraints, and implicit assumptions — things like channel de-prioritizations ("less focused on display"), budget ranges, methodology preferences (e.g. "directional spend ranges rather than exact figures"), and revision expectations.

### Step 11: AdditionalAgent

Searches for chunks tagged `additional_info`. Captures everything that doesn't fit elsewhere: links to external documents, stakeholder context from follow-up emails, leadership priorities, content requests, preferred tone, and any previous research references.

### Step 12: ExecutiveBriefAgent (Polish Pass)

Does **NOT** use the search index. Instead, it receives all 11 raw section outputs as a single prompt. Acting as a Senior Strategic Consultant, it de-duplicates facts across sections (each detail appears in exactly one section), tightens the tone to be leadership-ready, enforces consistent formatting (bold, bullets, tables), and returns the polished document with the same `[TAG]` structure. The orchestrator merges the polished output back over the raw sections.

### Step 13: Document Assembly & Cleanup

`DocumentBuilder` opens the Word template, fills in the metadata header table and each section's polished content, and produces a `.docx` file. `BlobService` uploads it to Azure Blob Storage. Finally, the orchestrator deletes all Foundry agents created for this session and clears the output cache.

---

## End-to-End Data Flow

### Full Generate Flow

```
  User clicks "Generate Full Document"
         │
         ▼
  POST /api/generate/full { session_id }
         │
         ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  AgentOrchestrator.generate_all(session_id)                  │
  │                                                              │
  │  for each SectionName (in enum order):                       │
  │    1. metadata        → MetadataAgent     → JSON             │
  │    2. client_brand    → ClientBrandAgent   → text            │
  │    3. project_overview → ProjectOverviewAgent → text         │
  │    4. objectives      → ObjectivesAgent    → text            │
  │    5. research_questions → ResearchQuestionsAgent → text     │
  │    6. data_timeframe  → DataTimeframeAgent → text            │
  │    7. research_usage  → ResearchUsageAgent → text            │
  │    8. deliverables    → DeliverablesAgent  → text            │
  │    9. timeline        → TimelineAgent      → text            │
  │   10. key_assumptions → KeyAssumptionsAgent → text           │
  │   11. additional_info → AdditionalAgent    → text            │
  │                                                              │
  │  Each agent: create in Foundry → thread → run → poll → parse │
  └──────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  DocumentBuilder.build(metadata, sections, session_id)       │
  │                                                              │
  │  Opens templates/research_brief_template.docx                │
  │  Fills in metadata fields + section content                  │
  │  Produces a .docx file in memory                             │
  └──────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  BlobService.upload_document(session_id, docx_bytes)         │
  │                                                              │
  │  Uploads to generated-docs/{session_id}.docx                 │
  └──────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  AgentOrchestrator.cleanup_session(session_id)               │
  │                                                              │
  │  Deletes all Foundry agents created for this session         │
  │  Clears output cache                                         │
  └──────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
  Response: { sections: [...], download_path: "/api/documents/..." }
```

### Human Review (Step-by-Step) Flow

```
  User steps through each section in the UI
         │
         ▼
  POST /api/generate/step { session_id, section }
         │
         ▼
  AgentOrchestrator.generate_section(session_id, section)
         │
         ▼
  Section appears in review panel
         │
         ├──► User edits content ──► PUT /api/sections/{session_id}/{section}
         │
         ├──► User adjusts tone  ──► POST /api/tone/adjust { content, preset }
         │                                    │
         │                                    ▼
         │                           ToneAgent rewrites text
         │                           (no search tool, just style transform)
         │
         ├──► User views diff    ──► DiffViewer component (client-side)
         │
         └──► User clicks "Approve & Next" ──► status = "approved", move to next
                                                  │
                                                  ▼ (after all sections approved)
                                     POST /api/documents/{session_id}/assemble
                                                  │
                                                  ▼
                                     GET /api/documents/{session_id}/download
```

---

## Project Structure

```
<project-root>/
  README.md                         # This file
  hubspot_deal_D-10482.json         # Example deal data
  [TEMPLATE] Research Brief...docx  # Reference template document

  infra/                            # Azure infrastructure
    setup-azure.ps1                 # Automated provisioning script
    teardown-azure.ps1              # Cleanup script
    README.md                       # Manual setup guide

  backend/                          # Python / FastAPI
    app/
      main.py                       # FastAPI app, CORS, router mounts
      config.py                     # Pydantic Settings (loads .env)

      routers/
        upload.py                   # POST /api/upload, /api/recreate-index
        sessions.py                 # GET /api/sessions
        generate.py                 # POST /api/generate/full, /step, section CRUD
        documents.py                # POST /assemble, GET /download, POST /tone/adjust
        debug.py                    # Debug endpoints (index inspection)

      services/
        blob_service.py             # Azure Blob Storage I/O
        search_service.py           # Two-tier chunking + AI Search indexing/querying
        enrichment_service.py       # Azure AI Language (key phrases, entities, sentiment)
        agent_orchestrator.py       # Agent lifecycle management + output caching
        document_builder.py         # python-docx template filling
        tone_service.py             # ToneAgent wrapper

      agents/
        base_agent.py               # Foundry agent base: create, run, poll, cleanup
        metadata_agent.py           # Extracts header metadata (returns JSON)
        client_brand_agent.py       # Client & brand identification
        project_overview_agent.py   # Research purpose and competitor scope
        objectives_agent.py         # Project objectives by category
        research_questions_agent.py # Research questions from deal data
        data_timeframe_agent.py     # Data timeframe statement
        research_usage_agent.py     # Who uses outputs and why
        deliverables_agent.py       # Expected output formats and structure
        timeline_agent.py           # Project timeline and milestones
        key_assumptions_agent.py    # Scope constraints and assumptions
        additional_agent.py         # Extra context, links, stakeholder notes
        tone_agent.py               # Style rewriting (no search tool)

      models/
        schemas.py                  # Pydantic models, enums, request/response types

    templates/
      research_brief_template.docx  # Word template for DocumentBuilder

    requirements.txt
    .env.example                    # Environment variable reference

  frontend/                         # React / TypeScript / Vite
    src/
      App.tsx                       # Router setup
      main.tsx                      # Entry point
      pages/
        HomePage.tsx                # Landing / navigation
        UploadPage.tsx              # JSON file upload
        FullGeneratePage.tsx        # One-click full generation
        HumanReviewPage.tsx         # Step-by-step review workflow
        DebugPage.tsx               # Index inspection tools
      components/
        SessionSelector.tsx         # Uploaded session picker
        SectionStepper.tsx          # Section navigation stepper
        SectionEditor.tsx           # Rich text editing for sections
        ToneAdjuster.tsx            # AI tone preset selector
        DiffViewer.tsx              # Before/after diff display
      services/
        api.ts                      # Axios client (baseURL: /api)
    vite.config.ts                  # Dev server port 5173, proxy to :8000
    package.json

  sample-data/
    earths-own-deal.json            # Example HubSpot JSON for testing
```

---

## Quick Start

### 1. Azure setup (IaC)

Provision Azure with the same automation the project is built around:

1. Install [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) and `az extension add --name ml`.
2. `az login` and select the right subscription.
3. If the resource group from [`infra/setup-azure.ps1`](infra/setup-azure.ps1) defaults does not exist yet, create it (example):  
   `az group create --name rg-proposal-poc --location canadacentral`
4. Run `infra/setup-azure.ps1` with **your own globally unique** resource names, **or** follow the manual CLI steps in [`infra/README.md`](infra/README.md).

This creates: storage + blob containers, Azure AI Search, Azure OpenAI (deployments), Azure AI Language, Azure AI Foundry hub + project, and Foundry connections (OpenAI + AI Search) for agent RAG. The script can write `backend/.env` for you; otherwise copy from `backend/.env.example` and fill in values.

### 2. Backend

```powershell
cd backend

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in your Azure credentials
cp .env.example .env
# Edit .env with your values from the Azure setup

# IMPORTANT: Log in to Azure (needed for DefaultAzureCredential used by Foundry agents)
az login

# Run the API server
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

### 3. Frontend

```powershell
cd frontend

# Install dependencies
npm install

# Run the dev server
npm run dev
```

The UI will be available at `http://localhost:5173`. It proxies `/api` requests to the backend.

---

## Usage

### Option 1: Full Generate

1. Go to **Upload** page and drop your HubSpot JSON file
2. Go to **Full Generate** page, select the session, click **Generate Full Document**
3. All 11 agents run sequentially, a Word document is assembled, and you can download it

### Option 2: Human Review (Step-by-Step)

1. Go to **Upload** page and drop your HubSpot JSON file
2. Go to **Human Review** page, select the session
3. Step through each section:
  - Click **Generate** to run the Foundry agent for that section
  - Review the output in the preview panel
  - Switch to **Edit** mode to make changes
  - Use the **AI Tone Adjuster** to restyle content (professional, concise, persuasive, leadership-ready, friendly)
  - Check the **Diff** view to see changes
  - Click **Approve & Next** to move forward
4. Once all sections are approved, click **Assemble Document** to download

---

## API Endpoints


| Method | Path                                   | Description                                          |
| ------ | -------------------------------------- | ---------------------------------------------------- |
| GET    | `/api/health`                          | Health check                                         |
| POST   | `/api/upload`                          | Upload HubSpot JSON → Blob Storage + AI Search index |
| POST   | `/api/recreate-index`                  | Drop and recreate the AI Search index                |
| GET    | `/api/sessions`                        | List uploaded sessions (from blob metadata)          |
| POST   | `/api/generate/full`                   | Generate all sections + assemble Word doc            |
| POST   | `/api/generate/step`                   | Generate a single section via Foundry agent          |
| GET    | `/api/sections/{session_id}`           | Get generated sections for a session                 |
| PUT    | `/api/sections/{session_id}/{section}` | Update section content (human edits)                 |
| POST   | `/api/sessions/{session_id}/cleanup`   | Delete Foundry agents for a session                  |
| POST   | `/api/documents/{session_id}/assemble` | Assemble Word doc from approved sections             |
| GET    | `/api/documents/{session_id}/download` | Download the generated Word doc                      |
| POST   | `/api/tone/adjust`                     | AI tone adjustment via ToneAgent                     |
| GET    | `/api/debug/`*                         | Debug endpoints for index inspection                 |


---

## Tech Stack

- **Frontend**: React 19, TypeScript, Vite, React Router, Lucide Icons
- **Backend**: Python, FastAPI, python-docx, Pydantic
- **AI Agents**: Azure AI Foundry Agent Service (`azure-ai-projects` SDK)
  - 11 section agents with `AzureAISearchTool` for native RAG
  - 1 tone adjustment agent (no search tool, rewrites content by style preset)
- **RAG Index**: Azure AI Search (HNSW vector search + semantic ranking + text search)
- **Enrichment**: Azure AI Language (key phrases, entities, sentiment)
- **LLM**: Azure OpenAI (e.g. `gpt-4o` for generation/classification, `text-embedding-3-small` for vectors — match your deployments)
- **Storage**: Azure Blob Storage (raw uploads + generated documents)
- **Auth**: `DefaultAzureCredential` (requires `az login` for local dev)

