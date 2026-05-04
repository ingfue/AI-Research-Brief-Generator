"""
Orchestrator that manages Foundry agent lifecycle per session.

For each generation request:
  1. Creates session-scoped agents in AI Foundry (with AzureAISearchTool
     filtered to session_id)
  2. Runs the agents via threads
  3. Parses tagged output from each agent
  4. Caches results to avoid duplicate runs
  5. Runs the ExecutiveBriefAgent to polish the full document
  6. Cleans up agents when the session is done
"""

import json
import re
import logging
from app.models.schemas import SectionName, SectionContent, SectionStatus, MetadataFields
from app.agents.metadata_agent import MetadataAgent
from app.agents.client_brand_agent import ClientBrandAgent
from app.agents.project_overview_agent import ProjectOverviewAgent
from app.agents.objectives_agent import ObjectivesAgent
from app.agents.research_questions_agent import ResearchQuestionsAgent
from app.agents.data_timeframe_agent import DataTimeframeAgent
from app.agents.research_usage_agent import ResearchUsageAgent
from app.agents.deliverables_agent import DeliverablesAgent
from app.agents.timeline_agent import TimelineAgent
from app.agents.key_assumptions_agent import KeyAssumptionsAgent
from app.agents.additional_agent import AdditionalAgent
from app.agents.executive_brief_agent import ExecutiveBriefAgent

logger = logging.getLogger(__name__)

SECTION_AGENT_MAP: dict[SectionName, tuple[type, str | None]] = {
    SectionName.METADATA: (MetadataAgent, None),
    SectionName.CLIENT_BRAND: (ClientBrandAgent, "CLIENT_BRAND"),
    SectionName.PROJECT_OVERVIEW: (ProjectOverviewAgent, "PROJECT_OVERVIEW"),
    SectionName.OBJECTIVES: (ObjectivesAgent, "OBJECTIVES"),
    SectionName.RESEARCH_QUESTIONS: (ResearchQuestionsAgent, "RESEARCH_QUESTIONS"),
    SectionName.DATA_TIMEFRAME: (DataTimeframeAgent, "DATA_TIMEFRAME"),
    SectionName.RESEARCH_USAGE: (ResearchUsageAgent, "RESEARCH_USAGE"),
    SectionName.DELIVERABLES: (DeliverablesAgent, "DELIVERABLES"),
    SectionName.TIMELINE: (TimelineAgent, "TIMELINE"),
    SectionName.KEY_ASSUMPTIONS: (KeyAssumptionsAgent, "KEY_ASSUMPTIONS"),
    SectionName.ADDITIONAL_INFO: (AdditionalAgent, "ADDITIONAL_INFO"),
}


def _flatten_to_string(value) -> str:
    """Convert a non-string value (list of dicts, list of strings, etc.) to a
    semicolon-separated string so it fits the MetadataFields schema."""
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(", ".join(f"{v}" for v in item.values() if v))
            else:
                parts.append(str(item))
        return "; ".join(parts)
    if isinstance(value, dict):
        return ", ".join(f"{v}" for v in value.values() if v)
    return str(value)


_TAG_TO_SECTION: dict[str, SectionName] = {
    "METADATA": SectionName.METADATA,
    "CLIENT_BRAND": SectionName.CLIENT_BRAND,
    "PROJECT_OVERVIEW": SectionName.PROJECT_OVERVIEW,
    "OBJECTIVES": SectionName.OBJECTIVES,
    "RESEARCH_QUESTIONS": SectionName.RESEARCH_QUESTIONS,
    "DATA_TIMEFRAME": SectionName.DATA_TIMEFRAME,
    "RESEARCH_USAGE": SectionName.RESEARCH_USAGE,
    "DELIVERABLES": SectionName.DELIVERABLES,
    "TIMELINE": SectionName.TIMELINE,
    "KEY_ASSUMPTIONS": SectionName.KEY_ASSUMPTIONS,
    "ADDITIONAL_INFO": SectionName.ADDITIONAL_INFO,
}

_SECTION_TO_TAG: dict[SectionName, str] = {v: k for k, v in _TAG_TO_SECTION.items()}


def _parse_tagged_output(raw: str, tag: str) -> str:
    """Extract content between [TAG] markers in agent output."""
    pattern = rf"\[{tag}\]\s*\n(.*?)(?=\n\[|$)"
    match = re.search(pattern, raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw.strip()


class AgentOrchestrator:
    """
    Manages Foundry agents per session.

    Each session gets its own set of agents (since the AzureAISearchTool
    filter is set at agent creation time with the session_id). Agents are
    cached for the session lifetime and cleaned up via cleanup_session().
    """

    def __init__(self):
        # session_id -> { agent_class_name -> agent_instance }
        self._agents: dict[str, dict[str, object]] = {}
        # session_id -> { agent_class_name -> raw_output }
        self._output_cache: dict[str, dict[str, str]] = {}
        self._polish_agent: ExecutiveBriefAgent | None = None

    def _get_or_create_agent(self, session_id: str, agent_class: type):
        """Get a cached agent or create a new one in Foundry for this session."""
        if session_id not in self._agents:
            self._agents[session_id] = {}

        class_name = agent_class.__name__
        if class_name not in self._agents[session_id]:
            agent = agent_class()
            agent.create(session_id)
            self._agents[session_id][class_name] = agent
            logger.info(f"Created Foundry agent: {class_name} for session {session_id}")

        return self._agents[session_id][class_name]

    def _get_output_cache(self, session_id: str) -> dict[str, str]:
        if session_id not in self._output_cache:
            self._output_cache[session_id] = {}
        return self._output_cache[session_id]

    def generate_metadata(self, session_id: str) -> MetadataFields:
        agent = self._get_or_create_agent(session_id, MetadataAgent)
        return agent.generate(session_id)

    def generate_section(self, session_id: str, section: SectionName) -> SectionContent:
        """Generate a single section via its dedicated Foundry agent."""
        if section == SectionName.METADATA:
            metadata = self.generate_metadata(session_id)
            return SectionContent(
                section=section,
                content=metadata.model_dump_json(indent=2),
                status=SectionStatus.REVIEW,
            )

        agent_class, tag = SECTION_AGENT_MAP[section]
        class_name = agent_class.__name__
        cache = self._get_output_cache(session_id)

        if class_name not in cache:
            agent = self._get_or_create_agent(session_id, agent_class)
            raw_output = agent.generate(session_id)
            cache[class_name] = raw_output
            logger.info(f"Agent {class_name} completed for session {session_id}")

        raw_output = cache[class_name]
        content = _parse_tagged_output(raw_output, tag) if tag else raw_output

        return SectionContent(
            section=section,
            content=content,
            status=SectionStatus.REVIEW,
        )

    def generate_all(self, session_id: str) -> list[SectionContent]:
        """Generate all sections in order via Foundry agents."""
        sections = []
        for section_name in SectionName:
            result = self.generate_section(session_id, section_name)
            sections.append(result)
        return sections

    def polish_brief(self, sections: list[SectionContent]) -> list[SectionContent]:
        """
        Run the ExecutiveBriefAgent over all generated sections to produce
        a polished, de-duplicated, leadership-ready document.

        Returns a new list of SectionContent with polished text replacing
        the raw agent outputs.  Sections the polishing agent chose to omit
        (no meaningful content) are preserved with their original text.
        """
        if not self._polish_agent:
            self._polish_agent = ExecutiveBriefAgent()

        raw_map: dict[str, str] = {}
        for sc in sections:
            tag = _SECTION_TO_TAG.get(sc.section)
            if tag:
                raw_map[tag] = sc.content

        logger.info("Starting Executive Brief polishing pass …")
        polished_map = self._polish_agent.polish(raw_map)
        logger.info(
            "Executive Brief polish complete — %d sections returned",
            len(polished_map),
        )

        section_by_name = {sc.section: sc for sc in sections}
        result: list[SectionContent] = []

        for section_name in SectionName:
            tag = _SECTION_TO_TAG.get(section_name)
            original = section_by_name.get(section_name)

            if tag and tag in polished_map:
                polished_content = polished_map[tag]

                if section_name == SectionName.METADATA and original:
                    polished_content = self._merge_metadata(
                        original.content, polished_content
                    )

                result.append(SectionContent(
                    section=section_name,
                    content=polished_content,
                    status=SectionStatus.REVIEW,
                ))
            elif original:
                result.append(original)

        return result

    @staticmethod
    def _merge_metadata(original_json: str, polished_raw: str) -> str:
        """
        The polishing agent returns metadata as JSON. Merge it with the
        original to ensure no fields are lost if the polish agent skipped any.
        Non-string values (lists, dicts) are flattened to strings so the
        result always conforms to MetadataFields.
        """
        try:
            original = json.loads(original_json)
        except (json.JSONDecodeError, TypeError):
            original = {}

        cleaned = polished_raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]

        try:
            polished = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            return original_json

        for k, v in polished.items():
            if v and not isinstance(v, str):
                polished[k] = _flatten_to_string(v)

        merged = {**original, **{k: v for k, v in polished.items() if v}}
        return json.dumps(merged, indent=2)

    def generate_all_polished(self, session_id: str) -> list[SectionContent]:
        """Generate all sections then run the executive brief polishing pass."""
        raw_sections = self.generate_all(session_id)
        return self.polish_brief(raw_sections)

    def cleanup_session(self, session_id: str):
        """Delete all Foundry agents created for a session."""
        agents = self._agents.pop(session_id, {})
        for class_name, agent in agents.items():
            try:
                agent.cleanup()
                logger.info(f"Cleaned up Foundry agent: {class_name} for session {session_id}")
            except Exception as e:
                logger.warning(f"Failed to clean up {class_name}: {e}")

        if self._polish_agent:
            try:
                self._polish_agent.cleanup()
            except Exception as e:
                logger.warning(f"Failed to clean up ExecutiveBriefAgent: {e}")
            self._polish_agent = None

        self._output_cache.pop(session_id, None)

    def clear_cache(self, session_id: str):
        """Clear cached outputs without deleting agents (for regeneration)."""
        self._output_cache.pop(session_id, None)
