import json
import logging
from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    GenerateRequest,
    StepGenerateRequest,
    SectionContent,
    SectionName,
    GenerateFullResponse,
    SectionStatus,
    MetadataFields,
)
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.document_builder import DocumentBuilder
from app.services.blob_service import BlobService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generate"])

# In-memory store for session sections (POC -- use a DB in production)
_session_sections: dict[str, dict[str, SectionContent]] = {}

# Shared orchestrator instance so Foundry agents are cached across requests
_orchestrator = AgentOrchestrator()


def _get_session_store(session_id: str) -> dict[str, SectionContent]:
    if session_id not in _session_sections:
        _session_sections[session_id] = {}
    return _session_sections[session_id]


@router.post("/generate/full", response_model=GenerateFullResponse)
async def generate_full(request: GenerateRequest):
    """Create Foundry agents, run all of them, polish via ExecutiveBriefAgent, and produce the Word document."""
    try:
        all_sections = _orchestrator.generate_all_polished(request.session_id)
    except Exception as e:
        logger.exception("Full generation failed")
        raise HTTPException(status_code=500, detail=f"Agent generation failed: {str(e)}")
    finally:
        _orchestrator.cleanup_session(request.session_id)

    store = _get_session_store(request.session_id)
    for sc in all_sections:
        sc.status = SectionStatus.APPROVED
        store[sc.section.value] = sc

    metadata_section = store.get(SectionName.METADATA.value)
    if not metadata_section:
        raise HTTPException(status_code=500, detail="Metadata generation failed")

    metadata = MetadataFields(**json.loads(metadata_section.content))

    section_texts = {}
    for name, sc in store.items():
        if name != SectionName.METADATA.value:
            section_texts[SectionName(name)] = sc.content

    builder = DocumentBuilder()
    doc_bytes = builder.build(metadata, section_texts)

    blob_service = BlobService()
    blob_service.upload_document(request.session_id, doc_bytes)

    return GenerateFullResponse(
        session_id=request.session_id,
        sections=all_sections,
        document_url=f"/api/documents/{request.session_id}/download",
    )


@router.post("/generate/step", response_model=SectionContent)
async def generate_step(request: StepGenerateRequest):
    """Create a Foundry agent for one section and generate it (human-review mode)."""
    try:
        result = _orchestrator.generate_section(request.session_id, request.section)
    except Exception as e:
        logger.exception("Step generation failed")
        raise HTTPException(status_code=500, detail=f"Agent generation failed: {str(e)}")

    store = _get_session_store(request.session_id)
    store[request.section.value] = result

    return result


@router.get("/sections/{session_id}", response_model=list[SectionContent])
async def get_sections(session_id: str):
    """Get all generated sections for a session."""
    store = _get_session_store(session_id)
    if not store:
        return []
    return list(store.values())


@router.put("/sections/{session_id}/{section}", response_model=SectionContent)
async def update_section(session_id: str, section: SectionName, body: dict):
    """Save human-edited section content."""
    store = _get_session_store(session_id)
    content = body.get("content", "")
    status = SectionStatus(body.get("status", "review"))

    sc = SectionContent(section=section, content=content, status=status)
    store[section.value] = sc
    return sc


@router.post("/sessions/{session_id}/cleanup")
async def cleanup_session(session_id: str):
    """Delete all Foundry agents created for a session."""
    _orchestrator.cleanup_session(session_id)
    return {"session_id": session_id, "status": "agents_cleaned_up"}
