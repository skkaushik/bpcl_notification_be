"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


# ─── Upload ────────────────────────────────────────────────────────────────────

class UploadData(BaseModel):
    session_id: str

class UploadResponse(BaseModel):
    success: bool = True
    message: str = "File uploaded successfully"
    data: UploadData

# ─── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""
    session_id: str
    message: str


class ChatData(BaseModel):
    message: str

class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    success: bool = True
    message: str = "Data fetched successfully"
    data: ChatData


class ChatHistoryItem(BaseModel):
    """A single message in the conversation history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── Analytics ─────────────────────────────────────────────────────────────────

class AnalyticsIntent(BaseModel):
    """Structured intent parsed from the LLM."""
    intent: str
    function_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    response_type: str = "summary"
    chart_config: Optional[dict[str, str]] = None


# ─── Email ──────────────────────────────────────────────────────────────────────

class EmailSendRequest(BaseModel):
    """
    Frontend sends session_id + filters only.
    The backend loads the data from session, applies filters, routes, and sends.
    """
    session_id: str
    ageFilter: int = 1

    # Filters (all optional — empty list = no filter = all)
    unitFilter: list[str] = Field(default_factory=list)
    typeFilter: list[str] = Field(default_factory=list)
    deptFilter: list[str] = Field(default_factory=list)
    userStatusFilter: list[str] = Field(default_factory=list)
    systemStatusFilter: list[str] = Field(default_factory=list)

    # Date range (ISO format strings, e.g. "2026-01-01")
    startDate: Optional[str] = None
    endDate: Optional[str] = None

class EmailSendResponse(BaseModel):
    success: bool = True
    message: str = "Emails sent successfully"
    details: Optional[dict] = None
