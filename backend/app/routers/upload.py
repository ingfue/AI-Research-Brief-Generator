import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models.schemas import UploadResponse
from app.services.blob_service import BlobService
from app.services.search_service import SearchService

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_json(file: UploadFile = File(...)):
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are accepted")

    content = await file.read()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if "deal" not in data and "activities" not in data:
        raise HTTPException(
            status_code=400,
            detail="JSON must contain 'deal' and/or 'activities' keys",
        )

    blob_service = BlobService()
    session_id, blob_name = blob_service.upload_json(content, file.filename)

    search_service = SearchService()
    chunk_count = search_service.chunk_and_index(session_id, data)

    return UploadResponse(
        session_id=session_id,
        filename=file.filename,
        status="indexed",
        chunk_count=chunk_count,
    )


@router.post("/recreate-index")
async def recreate_index():
    """Drop and recreate the search index (use after schema changes)."""
    search_service = SearchService()
    search_service.recreate_index()
    return {"status": "index_recreated", "index_name": search_service._index_name}
