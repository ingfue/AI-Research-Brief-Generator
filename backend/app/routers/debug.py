"""
Debug endpoints for inspecting the search index without calling GPT.

All endpoints are read-only and cost nothing — they query Azure AI Search
directly, bypassing the Foundry agents entirely.

Usage (after uploading a JSON):
  GET /api/debug/sessions                          — list all session IDs
  GET /api/debug/{session_id}/chunks               — all chunks for a session
  GET /api/debug/{session_id}/chunks/tier1          — only structural sub-chunks
  GET /api/debug/{session_id}/chunks/tier2          — only section aggregates
  GET /api/debug/{session_id}/section/{tag}         — chunks for a specific section
  GET /api/debug/{session_id}/section/{tag}/aggregate — the Tier-2 aggregate only
  GET /api/debug/{session_id}/search?q=...          — free-text search within session
  GET /api/debug/{session_id}/stats                 — chunk counts by type/tier/tag
"""

from fastapi import APIRouter, Query
from app.services.search_service import SearchService

router = APIRouter(prefix="/api/debug", tags=["debug"])

VALID_SECTION_TAGS = [
    "client_brand", "project_overview", "objectives", "research_questions",
    "data_timeframe", "research_usage", "deliverables", "timeline",
    "key_assumptions", "additional_info", "metadata",
]


def _svc() -> SearchService:
    return SearchService()


def _summarize_chunk(chunk: dict, full: bool = False) -> dict:
    """Return a view of a chunk. When *full* is False, content is previewed."""
    content = chunk.get("content", "")
    return {
        "chunk_id": chunk.get("chunk_id"),
        "chunk_type": chunk.get("chunk_type"),
        "chunk_tier": chunk.get("chunk_tier"),
        "section_tags": chunk.get("section_tags", []),
        "subject": chunk.get("subject"),
        "content": content if full else (content[:300] + "..." if len(content) > 300 else content),
        "content_length": len(content),
        "parent_chunk_id": chunk.get("parent_chunk_id"),
        "paragraph_index": chunk.get("paragraph_index"),
    }


@router.get("/sessions")
async def list_sessions():
    """List all distinct session IDs in the index."""
    svc = _svc()
    results = svc._search_client.search(
        search_text="*", top=100,
        select=["session_id", "chunk_id"],
    )
    sessions = {}
    for r in results:
        sid = r.get("session_id", "")
        sessions[sid] = sessions.get(sid, 0) + 1
    return {"sessions": [{"session_id": k, "chunk_count": v} for k, v in sessions.items()]}


@router.get("/{session_id}/chunks")
async def get_all_chunks(session_id: str):
    """Return all chunks for a session (both tiers)."""
    svc = _svc()
    chunks = svc.get_all_chunks(session_id)
    return {
        "session_id": session_id,
        "total_chunks": len(chunks),
        "chunks": [_summarize_chunk(c) for c in chunks],
    }


@router.get("/{session_id}/chunks/tier1")
async def get_tier1_chunks(session_id: str):
    """Return only Tier-1 structural sub-chunks."""
    svc = _svc()
    chunks = svc.search(session_id, query="*", top=50, chunk_tier="structural")
    return {
        "session_id": session_id,
        "tier": "structural",
        "total_chunks": len(chunks),
        "chunks": [_summarize_chunk(c) for c in chunks],
    }


@router.get("/{session_id}/chunks/tier2")
async def get_tier2_chunks(session_id: str):
    """Return only Tier-2 section aggregate chunks."""
    svc = _svc()
    chunks = svc.search(session_id, query="*", top=20, chunk_tier="section_aggregate")
    return {
        "session_id": session_id,
        "tier": "section_aggregate",
        "total_chunks": len(chunks),
        "chunks": [_summarize_chunk(c) for c in chunks],
    }


@router.get("/{session_id}/section/{tag}")
async def get_section_chunks(session_id: str, tag: str):
    """Return all chunks tagged for a specific section (full content)."""
    svc = _svc()
    chunks = svc.search(session_id, query="*", top=20, section_tag=tag)
    return {
        "session_id": session_id,
        "section_tag": tag,
        "total_chunks": len(chunks),
        "chunks": [_summarize_chunk(c, full=True) for c in chunks],
    }


@router.get("/{session_id}/section/{tag}/aggregate")
async def get_section_aggregate(session_id: str, tag: str):
    """Return ONLY the Tier-2 aggregate for a section (what agents see first)."""
    svc = _svc()
    chunks = svc.search(
        session_id, query="*", top=1,
        section_tag=tag, chunk_tier="section_aggregate",
    )
    if not chunks:
        return {"session_id": session_id, "section_tag": tag, "found": False}
    chunk = chunks[0]
    return {
        "session_id": session_id,
        "section_tag": tag,
        "found": True,
        "chunk_id": chunk.get("chunk_id"),
        "content_length": len(chunk.get("content", "")),
        "content": chunk.get("content"),
    }


@router.get("/{session_id}/search")
async def search_chunks(
    session_id: str,
    q: str = Query(..., description="Search query"),
    top: int = Query(5, ge=1, le=20),
    chunk_tier: str | None = Query(None),
    section_tag: str | None = Query(None),
):
    """Free-text search within a session (simulates what an agent sees)."""
    svc = _svc()
    chunks = svc.search(
        session_id, query=q, top=top,
        chunk_tier=chunk_tier, section_tag=section_tag,
    )
    return {
        "session_id": session_id,
        "query": q,
        "filters": {"chunk_tier": chunk_tier, "section_tag": section_tag},
        "total_results": len(chunks),
        "results": [_summarize_chunk(c, full=True) for c in chunks],
    }


@router.get("/{session_id}/stats")
async def get_session_stats(session_id: str):
    """Chunk counts broken down by type, tier, and section tag."""
    svc = _svc()
    chunks = svc.get_all_chunks(session_id)

    by_type: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    by_tag: dict[str, int] = {}

    for c in chunks:
        ct = c.get("chunk_type", "unknown")
        by_type[ct] = by_type.get(ct, 0) + 1

        tier = c.get("chunk_tier", "unknown")
        by_tier[tier] = by_tier.get(tier, 0) + 1

        for tag in c.get("section_tags", []):
            by_tag[tag] = by_tag.get(tag, 0) + 1

    return {
        "session_id": session_id,
        "total_chunks": len(chunks),
        "by_type": by_type,
        "by_tier": by_tier,
        "by_section_tag": by_tag,
        "available_tags": VALID_SECTION_TAGS,
    }
