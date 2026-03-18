"""TDD tests for rating and end-session API endpoints.

Tests verify:
- POST /api/sessions/{id}/rate — valid rating (1-5) updates DB
- POST /api/sessions/{id}/rate — rating outside 1-5 returns 422
- POST /api/sessions/{id}/rate — nonexistent session returns 404
- POST /api/sessions/{id}/end — calls LLM to summarize, returns summary
- POST /api/sessions/{id}/end — empty session returns empty summary
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

import anthropic
from httpx import ASGITransport, AsyncClient

from backend.app.config import Settings
from backend.app.db.database import Database
from backend.app.db.seed import seed_database
from backend.app.services.handbook import build_index
from backend.app.services.llm import LLMService
from backend.app.main import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(tmp_path):
    """Test client with seeded DB and mocked Anthropic client."""
    app = create_app()

    settings = Settings()

    db = Database(str(tmp_path / "test.db"))
    await db.connect()
    await seed_database(db)
    app.state.db = db

    handbook_index = build_index(settings.handbook_pdf_path, settings.handbook_index_path)
    app.state.handbook_index = handbook_index

    mock_client = AsyncMock(spec=anthropic.AsyncAnthropic)
    llm_service = LLMService(
        client=mock_client,
        model=settings.claude_model,
        handbook_index=handbook_index,
        db=db,
    )
    app.state.llm_service = llm_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db, mock_client

    await db.close()


async def _create_session(client: AsyncClient) -> str:
    """Helper: create a session and return the session_id."""
    resp = await client.get("/api/session/new")
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# Rate session tests
# ---------------------------------------------------------------------------

class TestRateSession:
    """Tests for POST /api/sessions/{id}/rate."""

    @pytest.mark.asyncio
    async def test_valid_rating_updates_db(self, client):
        ac, db, _ = client
        session_id = await _create_session(ac)

        resp = await ac.post(f"/api/sessions/{session_id}/rate", json={
            "rating": 4,
            "feedback": "Very helpful!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

        # Verify DB was updated
        row = await db.fetch_one(
            "SELECT rating, rating_feedback FROM sessions WHERE id = ?",
            (session_id,),
        )
        assert row["rating"] == 4
        assert row["rating_feedback"] == "Very helpful!"

    @pytest.mark.asyncio
    async def test_rating_without_feedback(self, client):
        ac, db, _ = client
        session_id = await _create_session(ac)

        resp = await ac.post(f"/api/sessions/{session_id}/rate", json={
            "rating": 5,
        })
        assert resp.status_code == 200

        row = await db.fetch_one(
            "SELECT rating, rating_feedback FROM sessions WHERE id = ?",
            (session_id,),
        )
        assert row["rating"] == 5
        assert row["rating_feedback"] is None

    @pytest.mark.asyncio
    async def test_rating_below_1_returns_422(self, client):
        ac, _, _ = client
        session_id = await _create_session(ac)

        resp = await ac.post(f"/api/sessions/{session_id}/rate", json={
            "rating": 0,
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_rating_above_5_returns_422(self, client):
        ac, _, _ = client
        session_id = await _create_session(ac)

        resp = await ac.post(f"/api/sessions/{session_id}/rate", json={
            "rating": 6,
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_rate_nonexistent_session_returns_404(self, client):
        ac, _, _ = client

        resp = await ac.post("/api/sessions/nonexistent-id/rate", json={
            "rating": 3,
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# End session tests
# ---------------------------------------------------------------------------

class TestEndSession:
    """Tests for POST /api/sessions/{id}/end."""

    @pytest.mark.asyncio
    async def test_end_session_returns_summary(self, client):
        ac, db, mock_client = client
        session_id = await _create_session(ac)

        # Insert some messages so end_session has content to summarize
        await db.insert(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, 'user', ?, ?)",
            (session_id, "What are your hours?", "2025-01-01T10:00:00"),
        )
        await db.insert(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, 'assistant', ?, ?)",
            (session_id, "We are open 7am to 6pm Monday through Friday.", "2025-01-01T10:00:01"),
        )

        # Mock Haiku response
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Parent asked about center hours. Informed of 7am-6pm M-F schedule."
        mock_response.content = [mock_text_block]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        resp = await ac.post(f"/api/sessions/{session_id}/end")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert len(data["summary"]) > 0

        # Verify DB was updated
        row = await db.fetch_one(
            "SELECT summary, ended_at FROM sessions WHERE id = ?",
            (session_id,),
        )
        assert row["summary"] is not None
        assert row["ended_at"] is not None

    @pytest.mark.asyncio
    async def test_end_empty_session_returns_empty_summary(self, client):
        ac, db, mock_client = client
        session_id = await _create_session(ac)

        # No messages for this session
        resp = await ac.post(f"/api/sessions/{session_id}/end")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == ""

        # Haiku should NOT have been called
        mock_client.messages.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_end_nonexistent_session_returns_404(self, client):
        ac, _, _ = client

        resp = await ac.post("/api/sessions/nonexistent-id/end")
        assert resp.status_code == 404
