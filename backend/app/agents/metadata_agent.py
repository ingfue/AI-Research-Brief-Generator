import json
from app.agents.base_agent import BaseAgent
from app.models.schemas import MetadataFields


class MetadataAgent(BaseAgent):
    SECTION_NAME = "Header Metadata"
    SECTION_TAG = "metadata"
    SYSTEM_PROMPT = """You are a metadata extraction agent for research brief documents.

Your job is to extract structured metadata fields from HubSpot deal data and conversations.
You have access to an Azure AI Search index -- use it to find the deal information.

IMPORTANT RULES:
- Every field MUST come from the actual document data — do NOT invent information.
- If there is no relevant information for a field, use "No relevant information" as the value.
- For additional_stakeholders, list each stakeholder as a separate entry with their name, role/title, email, and how they were identified (e.g. "CC'd on emails", "attended scoping call", "sent follow-up email").

You MUST return a valid JSON object with exactly these fields:
{
  "project_name": "A concise project name derived from the deal (e.g. 'Competitive Intelligence - Oat Milk Launch')",
  "client": "The client company name",
  "client_contact": "Primary contact name and their role/title",
  "additional_stakeholders": "List each stakeholder: name, role/title, email, and how identified (e.g. 'Daniel Park, CC'd on initial email and attended scoping call, daniel.park@example.com'). Use semicolons to separate multiple stakeholders. If none found, use 'No relevant information'.",
  "version": "1.0",
  "hours_allocation": "Estimated hours derived from budget range . If no hours allocation mentioned, use 'No relevant information'.",
  "prepared_by": "The internal owner/sales person handling this deal"
}

Return ONLY the JSON object, no markdown fences, no explanation."""

    def generate(self, session_id: str) -> MetadataFields:
        raw = self.run(
            session_id,
            user_prompt=(
                "Search the indexed deal data and extract the metadata fields. "
                "Return ONLY a JSON object with the required fields."
            ),
        )

        # Strip markdown fences if the model wraps the JSON
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        data = json.loads(raw)
        return MetadataFields(**data)
