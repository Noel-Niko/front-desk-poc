"""REST API endpoints for the AI Front Desk."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import pymupdf
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from backend.app.api.dependencies import get_db, get_llm_service
from backend.app.db.database import Database
from backend.app.models.schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    EndSessionResponse,
    RateSessionRequest,
    TourRequestBody,
    VerifyCodeRequest,
    VerifyCodeResponse,
)
from backend.app.services.llm import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    llm: LLMService = Depends(get_llm_service),
    db: Database = Depends(get_db),
) -> ChatResponse:
    """Process a text chat message and return the AI response."""
    # Ensure session exists in DB
    session = await db.fetch_one(
        "SELECT id FROM sessions WHERE id = ?", (request.session_id,)
    )
    if session is None:
        await db.insert(
            "INSERT INTO sessions (id, started_at, input_mode) VALUES (?, ?, 'text')",
            (request.session_id, datetime.now().isoformat()),
        )

    # Save user message
    await db.insert(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, 'user', ?, ?)",
        (request.session_id, request.message, datetime.now().isoformat()),
    )

    # Get LLM response
    result = await llm.chat(request.session_id, request.message)

    # Save assistant message
    citations_json = json.dumps(result["citations"]) if result["citations"] else None
    await db.insert(
        """INSERT INTO messages
           (session_id, role, content, citations, tool_used, timestamp)
           VALUES (?, 'assistant', ?, ?, ?, ?)""",
        (
            request.session_id,
            result["message"],
            citations_json,
            result["tool_used"],
            datetime.now().isoformat(),
        ),
    )

    # Update session if transferred
    if result["transferred"]:
        await db.execute(
            "UPDATE sessions SET transferred_to_human = 1, transfer_reason = ? WHERE id = ?",
            (result["transfer_reason"], request.session_id),
        )

    return ChatResponse(
        session_id=request.session_id,
        message=result["message"],
        citations=[Citation(**c) for c in result["citations"]],
        tool_used=result["tool_used"],
        transferred=result["transferred"],
        transfer_reason=result["transfer_reason"],
    )


@router.post("/verify-code", response_model=VerifyCodeResponse)
async def verify_code(
    request: VerifyCodeRequest,
    llm: LLMService = Depends(get_llm_service),
    db: Database = Depends(get_db),
) -> VerifyCodeResponse:
    """Verify a 4-digit security code to unlock child-specific data."""
    result = await llm.verify_security_code(request.session_id, request.code)

    # Update session with security code info
    if result["verified"]:
        await db.execute(
            "UPDATE sessions SET security_code_used = ?, child_id = ? WHERE id = ?",
            (request.code, result["child_id"], request.session_id),
        )

    return VerifyCodeResponse(
        verified=result["verified"],
        child_id=result.get("child_id"),
        child_name=result.get("child_name"),
        classroom=result.get("classroom"),
        error=result.get("error"),
    )


@router.get("/handbook/{page}")
async def get_handbook_page(
    page: int,
    llm: LLMService = Depends(get_llm_service),
) -> Response:
    """Serve a specific page of the handbook as a PNG image for citation display."""
    from backend.app.config import Settings

    settings = Settings()
    pdf_path = settings.handbook_pdf_path

    if not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail="Handbook PDF not found")

    doc = pymupdf.open(pdf_path)
    page_count = len(doc)
    if page < 1 or page > page_count:
        doc.close()
        raise HTTPException(
            status_code=404,
            detail=f"Page {page} not found (handbook has {page_count} pages)",
        )

    pdf_page = doc[page - 1]  # 0-indexed
    pix = pdf_page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    doc.close()

    return Response(content=img_bytes, media_type="image/png")


@router.post("/tour-request")
async def create_tour_request(
    request: TourRequestBody,
    db: Database = Depends(get_db),
) -> dict:
    """Submit a tour request directly (alternative to LLM-mediated flow)."""
    row_id = await db.insert(
        """INSERT INTO tour_requests
           (parent_name, parent_phone, parent_email, child_age,
            preferred_date, notes, created_at, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
        (
            request.parent_name,
            request.parent_phone,
            request.parent_email,
            request.child_age,
            request.preferred_date,
            request.notes,
            datetime.now().isoformat(),
        ),
    )
    return {"id": row_id, "status": "pending"}


@router.get("/session/new")
async def create_session(
    db: Database = Depends(get_db),
) -> dict:
    """Create a new chat session and return the session ID."""
    session_id = str(uuid.uuid4())
    await db.insert(
        "INSERT INTO sessions (id, started_at, input_mode) VALUES (?, ?, 'text')",
        (session_id, datetime.now().isoformat()),
    )
    return {"session_id": session_id}


@router.post("/sessions/{session_id}/rate")
async def rate_session(
    session_id: str,
    request: RateSessionRequest,
    db: Database = Depends(get_db),
) -> dict:
    """Rate a completed session (1-5 stars with optional feedback)."""
    # Validate rating range
    if request.rating < 1 or request.rating > 5:
        raise HTTPException(status_code=422, detail="Rating must be between 1 and 5")

    # Verify session exists
    session = await db.fetch_one("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.execute(
        "UPDATE sessions SET rating = ?, rating_feedback = ? WHERE id = ?",
        (request.rating, request.feedback, session_id),
    )
    return {"status": "ok"}


@router.post("/sessions/{session_id}/end", response_model=EndSessionResponse)
async def end_session(
    session_id: str,
    llm: LLMService = Depends(get_llm_service),
    db: Database = Depends(get_db),
) -> EndSessionResponse:
    """End a session, generating a summary via Claude Haiku."""
    # Verify session exists
    session = await db.fetch_one("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await llm.end_session(session_id)
    return EndSessionResponse(summary=result["summary"])
