"""FastAPI application factory with lifespan manager.

All singletons are initialized during startup and stored in app.state.
No global variables — dependencies are injected via Depends() in routes.
"""

import logging
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router as api_router
from backend.app.api.websocket import router as ws_router
from backend.app.config import Settings
from backend.app.db.database import Database
from backend.app.db.seed import seed_database
from backend.app.services.handbook import build_index
from backend.app.services.cartesia_tts import CartesiaTTSService
from backend.app.services.llm import LLMService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup and shutdown."""
    settings: Settings = app.state.settings

    # ── Startup ─────────────────────────────────────────────────────────
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    # 1. Database
    db = Database(settings.database_path)
    await db.connect()
    app.state.db = db

    # 2. Seed database if empty
    row = await db.fetch_one("SELECT COUNT(*) as cnt FROM children")
    if row and row["cnt"] == 0:
        logger.info("Database is empty — running seed data generator")
        await seed_database(db)

    # 3. Handbook RAG index
    logger.info("Loading handbook index...")
    handbook_index = build_index(settings.handbook_pdf_path, settings.handbook_index_path)
    app.state.handbook_index = handbook_index

    # 4. Anthropic client
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    app.state.anthropic_client = client

    # 5. LLM service
    llm_service = LLMService(
        client=client,
        model=settings.claude_model,
        handbook_index=handbook_index,
        db=db,
    )
    app.state.llm_service = llm_service

    # 6. TTS service (optional — only if Cartesia API key is configured)
    tts_service = None
    if settings.cartesia_api_key:
        tts_service = CartesiaTTSService(
            api_key=settings.cartesia_api_key,
            voice_id=settings.cartesia_voice_id,
        )
        logger.info("Cartesia TTS service initialized (voice: %s)", settings.cartesia_voice_id)
    else:
        logger.info("No Cartesia API key — TTS disabled")
    app.state.tts_service = tts_service

    logger.info("Application started — ready to serve")

    yield

    # ── Shutdown ────────────────────────────────────────────────────────
    if tts_service:
        await tts_service.close()
    await db.close()
    logger.info("Application shut down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = Settings()

    app = FastAPI(
        title="BrightWheel AI Front Desk",
        description="Voice-first AI assistant for Sunshine Learning Center",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Store settings in app.state for lifespan access
    app.state.settings = settings

    # CORS (allow local frontend dev server)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(api_router)
    app.include_router(ws_router)

    return app
