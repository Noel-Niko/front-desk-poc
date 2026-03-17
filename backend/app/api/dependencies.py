"""FastAPI dependency injection functions.

All singletons are stored in app.state during lifespan startup.
These functions retrieve them for route handlers via Depends().
"""

from fastapi import Request

from backend.app.db.database import Database
from backend.app.services.handbook import HandbookIndex
from backend.app.services.llm import LLMService


def get_db(request: Request) -> Database:
    """Get the database instance from app state."""
    return request.app.state.db


def get_handbook_index(request: Request) -> HandbookIndex:
    """Get the handbook FAISS+BM25 index from app state."""
    return request.app.state.handbook_index


def get_llm_service(request: Request) -> LLMService:
    """Get the LLM service (Claude + tools) from app state."""
    return request.app.state.llm_service
