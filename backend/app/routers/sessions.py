from fastapi import APIRouter
from app.models.schemas import SessionInfo
from app.services.blob_service import BlobService

router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions():
    """List all uploaded sessions."""
    blob_service = BlobService()
    sessions = blob_service.list_sessions()
    return [SessionInfo(**s) for s in sessions]
