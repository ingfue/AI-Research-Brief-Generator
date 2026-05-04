"""
Tone adjustment agent backed by Azure AI Foundry.

Unlike the section agents, this agent does NOT use AzureAISearchTool --
it only needs the text and a tone instruction, no RAG context.
"""

import time
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MessageTextContent, RunStatus
from azure.identity import DefaultAzureCredential
from app.config import get_settings

TONE_PRESETS = {
    "professional": "Rewrite this text in a highly professional, business-appropriate tone. Keep it clear and authoritative.",
    "concise": "Rewrite this text to be as concise as possible. Remove redundancy, tighten sentences, keep all key information.",
    "persuasive": "Rewrite this text to be more persuasive and compelling. Emphasize value and impact.",
    "leadership-ready": "Rewrite this text so it is suitable for a C-suite or leadership audience. Focus on strategic implications, be direct, and avoid jargon.",
    "friendly": "Rewrite this text in a warm, approachable, yet professional tone.",
}

SYSTEM_PROMPT = (
    "You are a professional editor. Your job is to adjust the tone of text "
    "while preserving all factual content and meaning. Return ONLY the "
    "rewritten text, nothing else -- no preamble, no explanation."
)


class ToneAgent:
    def __init__(self):
        settings = get_settings()
        self._client = AIProjectClient.from_connection_string(
            credential=DefaultAzureCredential(),
            conn_str=settings.azure_ai_project_connection_string,
        )
        self._model = settings.azure_ai_model_deployment
        self._agent_id: str | None = None

    def _ensure_agent(self):
        if self._agent_id:
            return
        agent = self._client.agents.create_agent(
            model=self._model,
            name="ToneAdjustmentAgent",
            instructions=SYSTEM_PROMPT,
        )
        self._agent_id = agent.id

    def adjust(self, text: str, tone: str, custom_instruction: str | None = None) -> str:
        self._ensure_agent()

        instruction = custom_instruction or TONE_PRESETS.get(
            tone.lower(), f"Rewrite this text with a {tone} tone."
        )

        thread = self._client.agents.create_thread()

        self._client.agents.create_message(
            thread_id=thread.id,
            role="user",
            content=f"{instruction}\n\n---\n\n{text}",
        )

        run = self._client.agents.create_run(
            thread_id=thread.id,
            agent_id=self._agent_id,
        )

        run = self._poll_run(thread.id, run.id)

        if run.status != RunStatus.COMPLETED:
            raise RuntimeError(f"Tone agent run failed: {run.status}")

        messages = self._client.agents.list_messages(thread_id=thread.id)
        for msg in messages.data:
            if msg.role == "assistant":
                for block in msg.content:
                    if isinstance(block, MessageTextContent):
                        return block.text.value.strip()
        return text

    def cleanup(self):
        if self._agent_id:
            try:
                self._client.agents.delete_agent(self._agent_id)
            except Exception:
                pass
            self._agent_id = None

    def _poll_run(self, thread_id: str, run_id: str, timeout: int = 60):
        terminal = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.EXPIRED}
        start = time.time()
        while time.time() - start < timeout:
            run = self._client.agents.get_run(thread_id=thread_id, run_id=run_id)
            if run.status in terminal:
                return run
            time.sleep(1)
        raise TimeoutError("Tone agent run timed out")
