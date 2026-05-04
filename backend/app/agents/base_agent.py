"""
Base agent backed by Azure AI Foundry Agent Service.

Each agent is created as a real resource in AI Foundry with an
AzureAISearchTool configured for session-scoped RAG. The index uses
a two-tier chunking strategy:

  Tier 1 — "structural"         Fine-grained sub-chunks (paragraphs,
                                 meeting-note headings, deal field groups).
  Tier 2 — "section_aggregate"  One pre-assembled chunk per template
                                 section, combining all Tier-1 text
                                 classified for that section.

Agents should search for the section_aggregate chunk first (clean,
de-duplicated view) and fall back to structural sub-chunks when more
granular detail is needed.

Lifecycle:
  1. create()   -- registers the agent in Foundry with session filter
  2. run()      -- creates a thread, sends the prompt, executes the run
  3. cleanup()  -- deletes the agent from Foundry when done
"""

import logging
import re
import time
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AzureAISearchTool,
    AzureAISearchQueryType,
    MessageTextContent,
    RunStatus,
)
from azure.identity import DefaultAzureCredential
from app.config import get_settings

logger = logging.getLogger(__name__)

_RATE_LIMIT_KEYWORDS = ("429", "rate limit", "quota", "throttl", "too many requests")
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 60


def _is_rate_limited(error) -> bool:
    """Check whether an exception or error message indicates a rate-limit hit."""
    msg = str(error).lower()
    return any(kw in msg for kw in _RATE_LIMIT_KEYWORDS)


class BaseAgent:
    SECTION_NAME: str = ""
    SECTION_TAG: str = ""
    SYSTEM_PROMPT: str = ""

    def __init__(self):
        settings = get_settings()
        self._project_client = AIProjectClient.from_connection_string(
            credential=DefaultAzureCredential(),
            conn_str=settings.azure_ai_project_connection_string,
        )
        self._model = settings.azure_ai_model_deployment
        self._search_conn_name = settings.azure_ai_search_connection_name
        self._index_name = settings.azure_search_index_name
        self._agent_id: str | None = None

    # ------------------------------------------------------------------
    # Agent lifecycle
    # ------------------------------------------------------------------

    def create(self, session_id: str) -> str:
        """Register this agent in AI Foundry with a session-scoped search tool."""
        search_tool = self._build_search_tool(session_id)

        agent = self._project_client.agents.create_agent(
            model=self._model,
            name=f"{self.__class__.__name__}_{session_id}",
            instructions=self.SYSTEM_PROMPT,
            tools=search_tool.definitions,
            tool_resources=search_tool.resources,
        )
        self._agent_id = agent.id
        return agent.id

    def cleanup(self):
        """Delete the agent from Foundry."""
        if self._agent_id:
            try:
                self._project_client.agents.delete_agent(self._agent_id)
            except Exception:
                pass
            self._agent_id = None

    # ------------------------------------------------------------------
    # Generation via threads + runs
    # ------------------------------------------------------------------

    def run(self, session_id: str, user_prompt: str | None = None) -> str:
        """
        Create a thread, send a message, execute the agent, and return
        the response text.  Automatically creates the agent if needed.

        Retries up to MAX_RETRIES times when a rate-limit (429) is detected
        — either from the API call itself or from the run's error status.
        """
        if not self._agent_id:
            self.create(session_id)

        prompt = user_prompt or (
            f"Generate the '{self.SECTION_NAME}' section of the research brief "
            f"using the indexed HubSpot deal data, emails, and meeting notes.\n\n"
            f"SEARCH STRATEGY: Run MULTIPLE searches using different keyword "
            f"combinations relevant to '{self.SECTION_NAME}'. The data is spread "
            f"across deal fields, email threads, and meeting notes — a single search "
            f"will NOT find everything. Try at least 3 different search queries with "
            f"varied terms before writing.\n\n"
            f"STRICT GROUNDING: Use **ONLY** actual names, dates, and details found "
            f"in the search results. Do not use placeholders or generic terms. If "
            f"information is not found after multiple searches, omit that bullet "
            f"rather than writing 'No relevant information'.\n\n"
            f"STRUCTURE & FORMATTING:\n"
            f"- Present information as a **structured list** categorized by relevance.\n"
            f"- Use **Bold Markdown** for key terms, names, or category labels.\n"
            f"- Use '- ' for bullet points to ensure a clean, scannable layout.\n"
            f"- Do not include the section heading itself or any source citations."
        )

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                thread = self._project_client.agents.create_thread()
                self._project_client.agents.create_message(
                    thread_id=thread.id,
                    role="user",
                    content=prompt,
                )
                run = self._project_client.agents.create_run(
                    thread_id=thread.id,
                    agent_id=self._agent_id,
                )
            except Exception as exc:
                if _is_rate_limited(exc) and attempt < MAX_RETRIES:
                    logger.warning(
                        "Rate-limited on %s (attempt %d/%d), waiting %ds …",
                        self.__class__.__name__, attempt, MAX_RETRIES, RETRY_WAIT_SECONDS,
                    )
                    time.sleep(RETRY_WAIT_SECONDS)
                    continue
                raise

            run = self._poll_run(thread.id, run.id)

            if run.status == RunStatus.COMPLETED:
                return self._extract_response(thread.id)

            error_msg = run.last_error.message if run.last_error else str(run.status)
            if _is_rate_limited(error_msg) and attempt < MAX_RETRIES:
                logger.warning(
                    "Rate-limited run on %s (attempt %d/%d): %s — waiting %ds …",
                    self.__class__.__name__, attempt, MAX_RETRIES,
                    error_msg, RETRY_WAIT_SECONDS,
                )
                time.sleep(RETRY_WAIT_SECONDS)
                last_error = error_msg
                continue

            raise RuntimeError(
                f"Agent run failed with status '{run.status}': {error_msg}"
            )

        raise RuntimeError(
            f"Agent {self.__class__.__name__} exhausted {MAX_RETRIES} retries "
            f"(last error: {last_error})"
        )

    def generate(self, session_id: str) -> str:
        """Public API matching the orchestrator's expectations."""
        return self.run(session_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_search_tool(self, session_id: str) -> AzureAISearchTool:
        """Build an AzureAISearchTool scoped to a single session.

        Applies three critical parameters that were previously missing:
          - filter:     OData filter scoping results to this session_id
          - query_type: vector_semantic_hybrid for best retrieval quality
          - top_k:      limit results to avoid flooding the agent context
        """
        conn = self._project_client.connections.get(
            connection_name=self._search_conn_name,
        )
        search_tool = AzureAISearchTool(
            index_connection_id=conn.id,
            index_name=self._index_name,
            query_type=AzureAISearchQueryType.SIMPLE,
            top_k=5,
            filter=f"session_id eq '{session_id}'",
        )
        return search_tool

    def _poll_run(self, thread_id: str, run_id: str, timeout: int = 240):
        """Poll until the run reaches a terminal state."""
        terminal = {
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.EXPIRED,
        }
        start = time.time()
        while time.time() - start < timeout:
            run = self._project_client.agents.get_run(
                thread_id=thread_id,
                run_id=run_id,
            )
            if run.status in terminal:
                return run
            time.sleep(1)
        raise TimeoutError(f"Agent run did not complete within {timeout}s")

    def _extract_response(self, thread_id: str) -> str:
        """Pull the last assistant message from the thread."""
        messages = self._project_client.agents.list_messages(thread_id=thread_id)
        for msg in messages.data:
            if msg.role == "assistant":
                parts = []
                for block in msg.content:
                    if isinstance(block, MessageTextContent):
                        parts.append(block.text.value)
                raw = "\n".join(parts).strip()
                return self._clean_output(raw)
        return ""

    @staticmethod
    def _clean_output(text: str) -> str:
        """Strip citation markers and markdown formatting from agent output, preserving bullet points."""
        text = re.sub(r"【[^】]*】", "", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
        # Normalize bullet characters (•) to plain dashes
        text = re.sub(r"^•\s+", "- ", text, flags=re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
