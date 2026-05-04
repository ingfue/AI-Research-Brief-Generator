import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.models.schemas import SectionName, SectionContent, MetadataFields, ToneAdjustRequest, ToneAdjustResponse
from app.services.blob_service import BlobService
from app.services.document_builder import DocumentBuilder
from app.services.tone_service import ToneService
from app.services.agent_orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["documents"])

# Reference the same in-memory store from generate router
from app.routers.generate import _session_sections

_orchestrator = AgentOrchestrator()


@router.post("/documents/{session_id}/assemble")
async def assemble_document(session_id: str, polish: bool = True):
    """Assemble Word doc from all approved/reviewed sections.

    When polish=True (default), the sections are run through the
    ExecutiveBriefAgent for a final polishing pass before assembly.
    """
    store = _session_sections.get(session_id, {})
    if not store:
        raise HTTPException(status_code=404, detail="No sections found for this session")

    metadata_section = store.get(SectionName.METADATA.value)
    if not metadata_section:
        raise HTTPException(status_code=400, detail="Metadata section is missing")

    sections_list = list(store.values())

    if polish:
        try:
            sections_list = _orchestrator.polish_brief(sections_list)
            for sc in sections_list:
                store[sc.section.value] = sc
            metadata_section = store.get(SectionName.METADATA.value)
        except Exception as e:
            logger.warning("Polish pass failed, assembling with raw sections: %s", e)

    metadata = MetadataFields(**json.loads(metadata_section.content))

    section_texts = {}
    for name, sc in store.items():
        if name != SectionName.METADATA.value:
            section_texts[SectionName(name)] = sc.content

    builder = DocumentBuilder()
    doc_bytes = builder.build(metadata, section_texts)

    blob_service = BlobService()
    blob_service.upload_document(session_id, doc_bytes)

    return {"session_id": session_id, "status": "assembled", "download_url": f"/api/documents/{session_id}/download"}


@router.get("/documents/{session_id}/download")
async def download_document(session_id: str):
    """Download the generated Word document."""
    try:
        blob_service = BlobService()
        doc_bytes = blob_service.download_document(session_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Document not found")

    return Response(
        content=doc_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{session_id}_proposal.docx"'},
    )


@router.post("/tone/adjust", response_model=ToneAdjustResponse)
async def adjust_tone(request: ToneAdjustRequest):
    """Adjust the tone of text using AI."""
    tone_service = ToneService()

    try:
        adjusted = tone_service.adjust_tone(
            text=request.text,
            tone=request.tone,
            custom_instruction=request.custom_instruction,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tone adjustment failed: {str(e)}")

    return ToneAdjustResponse(
        original=request.text,
        adjusted=adjusted,
        tone=request.tone,
    )
