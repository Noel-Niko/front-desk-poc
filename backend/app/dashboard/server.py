"""Operator Dashboard — separate FastAPI app on port 8001.

Reads from the same SQLite database as the main backend.
Self-contained HTML/CSS/JS served from template.py.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from backend.app.config import Settings
from backend.app.db.database import Database
from backend.app.dashboard.service import DashboardService
from backend.app.dashboard.template import DASHBOARD_HTML

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage dashboard lifecycle."""
    settings: Settings = app.state.settings

    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    db = Database(settings.database_path)
    await db.connect()
    app.state.db = db

    logger.info("Dashboard started — connected to database")
    yield

    await db.close()
    logger.info("Dashboard shut down")


def create_app() -> FastAPI:
    """Create the operator dashboard FastAPI app."""
    settings = Settings()

    app = FastAPI(
        title="BrightWheel Operator Dashboard",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_db(request: Request) -> Database:
        return request.app.state.db

    def get_service(request: Request) -> DashboardService:
        return DashboardService(request.app.state.db)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard_html():
        """Serve the dashboard HTML page."""
        return DASHBOARD_HTML

    @app.get("/api/sessions")
    async def list_sessions(
        request: Request,
        min_rating: int | None = None,
        transferred_only: bool = False,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        """List sessions with optional filters."""
        service = get_service(request)
        return await service.list_sessions(
            min_rating=min_rating,
            transferred_only=transferred_only,
            date_from=date_from,
            date_to=date_to,
        )

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str, request: Request):
        """Get session detail with messages."""
        service = get_service(request)
        result = await service.get_session(session_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return result

    @app.get("/api/stats")
    async def get_stats(request: Request):
        """Get dashboard KPI stats."""
        service = get_service(request)
        return await service.get_stats()

    @app.get("/api/struggles")
    async def get_struggles(request: Request):
        """Get sessions where the system struggled."""
        service = get_service(request)
        return await service.get_struggles()

    @app.get("/api/faq-overrides")
    async def list_faq_overrides(request: Request):
        """List all FAQ overrides."""
        service = get_service(request)
        return await service.list_faq_overrides()

    @app.post("/api/faq-overrides", status_code=201)
    async def create_faq_override(request: Request):
        """Create a new FAQ override."""
        body = await request.json()
        service = get_service(request)
        return await service.create_faq_override(
            question_pattern=body["question_pattern"],
            answer=body["answer"],
        )

    @app.put("/api/faq-overrides/{override_id}")
    async def update_faq_override(override_id: int, request: Request):
        """Update an existing FAQ override."""
        body = await request.json()
        service = get_service(request)
        result = await service.update_faq_override(override_id, body)
        if result is None:
            raise HTTPException(status_code=404, detail="Override not found")
        return result

    @app.delete("/api/faq-overrides/{override_id}")
    async def delete_faq_override(override_id: int, request: Request):
        """Delete a FAQ override."""
        service = get_service(request)
        await service.delete_faq_override(override_id)
        return {"status": "deleted"}

    @app.get("/api/rating-distribution")
    async def get_rating_distribution(request: Request):
        """Get rating distribution (count per 1-5 stars)."""
        service = get_service(request)
        return await service.get_rating_distribution()

    @app.get("/api/citation-frequency")
    async def get_citation_frequency(request: Request):
        """Get most frequently cited handbook pages."""
        service = get_service(request)
        return await service.get_citation_frequency()

    @app.get("/api/low-rating-sessions")
    async def get_low_rating_sessions(request: Request):
        """Get sessions rated 2 or below that need attention."""
        service = get_service(request)
        return await service.get_low_rating_sessions()

    @app.get("/api/tour-requests")
    async def list_tour_requests(request: Request):
        """List pending tour requests."""
        service = get_service(request)
        return await service.list_tour_requests()

    return app
