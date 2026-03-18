"""Pydantic request/response models for the API."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """POST /api/chat request body."""

    session_id: str
    message: str
    security_code: str | None = None  # Set after verification


class Citation(BaseModel):
    """A single handbook citation."""

    page: int
    section: str
    text: str


class ChatResponse(BaseModel):
    """POST /api/chat response body."""

    session_id: str
    message: str
    citations: list[Citation] = []
    tool_used: str | None = None
    transferred: bool = False
    transfer_reason: str | None = None


class VerifyCodeRequest(BaseModel):
    """POST /api/verify-code request body."""

    session_id: str
    code: str


class VerifyCodeResponse(BaseModel):
    """POST /api/verify-code response body."""

    verified: bool
    child_id: int | None = None
    child_name: str | None = None
    classroom: str | None = None
    error: str | None = None


class TourRequestBody(BaseModel):
    """POST /api/tour-request request body."""

    parent_name: str
    parent_phone: str
    parent_email: str | None = None
    child_age: int | None = None
    preferred_date: str
    notes: str | None = None


class RateSessionRequest(BaseModel):
    """POST /api/sessions/{id}/rate request body."""

    rating: int
    feedback: str | None = None


class EndSessionResponse(BaseModel):
    """POST /api/sessions/{id}/end response body."""

    summary: str
