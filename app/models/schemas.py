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
