from pydantic import BaseModel
from typing import Optional
from enum import Enum


class SectionName(str, Enum):
    METADATA = "metadata"
    CLIENT_BRAND = "client_brand"
    PROJECT_OVERVIEW = "project_overview"
    OBJECTIVES = "objectives"
    RESEARCH_QUESTIONS = "research_questions"
    DATA_TIMEFRAME = "data_timeframe"
    RESEARCH_USAGE = "research_usage"
    DELIVERABLES = "deliverables"
    TIMELINE = "timeline"
    KEY_ASSUMPTIONS = "key_assumptions"
    ADDITIONAL_INFO = "additional_info"


class SectionStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    REVIEW = "review"
    APPROVED = "approved"


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    status: str
    chunk_count: int


class SessionInfo(BaseModel):
    session_id: str
    filename: str
    created_at: str
    status: str


class GenerateRequest(BaseModel):
    session_id: str


class StepGenerateRequest(BaseModel):
    session_id: str
    section: SectionName


class SectionContent(BaseModel):
    section: SectionName
    content: str
    status: SectionStatus = SectionStatus.REVIEW


class SectionUpdateRequest(BaseModel):
    content: str


class ToneAdjustRequest(BaseModel):
    text: str
    tone: str  # e.g. "professional", "concise", "persuasive", "leadership-ready"
    custom_instruction: Optional[str] = None


class ToneAdjustResponse(BaseModel):
    original: str
    adjusted: str
    tone: str


class GenerateFullResponse(BaseModel):
    session_id: str
    sections: list[SectionContent]
    document_url: str


class MetadataFields(BaseModel):
    project_name: str = ""
    client: str = ""
    client_contact: str = ""
    additional_stakeholders: str = ""
    version: str = "1.0"
    hours_allocation: str = ""
    prepared_by: str = ""
