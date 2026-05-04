from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import upload, generate, documents, sessions, debug

app = FastAPI(
    title="Proposal Generator POC",
    description="Generate research brief documents from HubSpot deal data using AI agents",
    version="0.1.0",
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(sessions.router)
app.include_router(generate.router)
app.include_router(documents.router)
app.include_router(debug.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "proposal-generator"}
