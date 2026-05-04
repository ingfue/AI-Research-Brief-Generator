import uuid
import json
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient, ContentSettings
from app.config import get_settings


class BlobService:
    def __init__(self):
        settings = get_settings()
        self._client = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
        self._uploads_container = settings.blob_container_uploads
        self._docs_container = settings.blob_container_docs

    def upload_json(self, file_content: bytes, original_filename: str) -> tuple[str, str]:
        """Upload JSON to blob storage. Returns (session_id, blob_name)."""
        session_id = uuid.uuid4().hex[:12]
        blob_name = f"{session_id}.json"

        container_client = self._client.get_container_client(self._uploads_container)
        container_client.upload_blob(
            name=blob_name,
            data=file_content,
            overwrite=True,
            metadata={
                "session_id": session_id,
                "original_filename": original_filename,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return session_id, blob_name

    def get_json(self, session_id: str) -> dict:
        """Download and parse JSON from blob storage."""
        blob_name = f"{session_id}.json"
        container_client = self._client.get_container_client(self._uploads_container)
        blob_data = container_client.download_blob(blob_name).readall()
        return json.loads(blob_data)

    def upload_document(self, session_id: str, doc_bytes: bytes) -> str:
        """Upload generated Word doc to blob storage. Returns the blob URL."""
        blob_name = f"{session_id}_proposal.docx"
        container_client = self._client.get_container_client(self._docs_container)
        container_client.upload_blob(
            name=blob_name,
            data=doc_bytes,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        )
        return blob_name

    def download_document(self, session_id: str) -> bytes:
        """Download generated Word doc."""
        blob_name = f"{session_id}_proposal.docx"
        container_client = self._client.get_container_client(self._docs_container)
        return container_client.download_blob(blob_name).readall()

    def list_sessions(self) -> list[dict]:
        """List all uploaded sessions with metadata."""
        container_client = self._client.get_container_client(self._uploads_container)
        sessions = []
        for blob in container_client.list_blobs(include=["metadata"]):
            if blob.name.endswith(".json"):
                meta = blob.metadata or {}
                sessions.append({
                    "session_id": meta.get("session_id", blob.name.replace(".json", "")),
                    "filename": meta.get("original_filename", blob.name),
                    "created_at": meta.get("uploaded_at", str(blob.creation_time)),
                    "status": "indexed",
                })
        return sessions
