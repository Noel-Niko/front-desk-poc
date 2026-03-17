"""Integration tests for the chat API endpoint."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

import anthropic
from httpx import ASGITransport, AsyncClient

from backend.app.config import Settings
from backend.app.db.database import Database
from backend.app.db.seed import seed_database
from backend.app.services.handbook import build_index
from backend.app.services.llm import LLMService
from backend.app.main import create_app


@pytest_asyncio.fixture
async def client(tmp_path):
    """Create a test client with manually initialized app state.

    Bypasses lifespan (httpx ASGITransport doesn't trigger it) by
    wiring up app.state directly.
    """
    app = create_app()

    # Initialize state manually (mirrors lifespan startup)
    settings = Settings()

    db = Database(str(tmp_path / "test.db"))
    await db.connect()
    await seed_database(db)
    app.state.db = db

    handbook_index = build_index(settings.handbook_pdf_path, settings.handbook_index_path)
    app.state.handbook_index = handbook_index

    # Use a real Anthropic client (the LLM chat tests would need mocking
    # for unit tests, but verify-code and handbook don't call the LLM)
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
        yield ac

    await db.close()


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_creates_session_with_uuid(self, client: AsyncClient) -> None:
        resp = await client.get("/api/session/new")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 10  # UUID length


class TestVerifyCode:
    @pytest.mark.asyncio
    async def test_valid_code_returns_child_info(self, client: AsyncClient) -> None:
        # Create session first
        session_resp = await client.get("/api/session/new")
        session_id = session_resp.json()["session_id"]

        resp = await client.post("/api/verify-code", json={
            "session_id": session_id,
            "code": "7291",  # Sofia Martinez's code
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is True
        assert "Sofia" in data["child_name"]
        assert data["classroom"] == "Butterfly Room"

    @pytest.mark.asyncio
    async def test_invalid_code_returns_error(self, client: AsyncClient) -> None:
        session_resp = await client.get("/api/session/new")
        session_id = session_resp.json()["session_id"]

        resp = await client.post("/api/verify-code", json={
            "session_id": session_id,
            "code": "0000",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is False
        assert data["error"] is not None

    @pytest.mark.asyncio
    async def test_three_failures_locks_out(self, client: AsyncClient) -> None:
        session_resp = await client.get("/api/session/new")
        session_id = session_resp.json()["session_id"]

        for _ in range(3):
            await client.post("/api/verify-code", json={
                "session_id": session_id, "code": "0000",
            })

        # 4th attempt should be locked
        resp = await client.post("/api/verify-code", json={
            "session_id": session_id, "code": "7291",  # Even correct code
        })
        data = resp.json()
        assert data["verified"] is False
        assert "Too many" in data["error"]


class TestHandbookPage:
    @pytest.mark.asyncio
    async def test_valid_page_returns_png(self, client: AsyncClient) -> None:
        resp = await client.get("/api/handbook/1")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    @pytest.mark.asyncio
    async def test_invalid_page_returns_404(self, client: AsyncClient) -> None:
        resp = await client.get("/api/handbook/999")
        assert resp.status_code == 404
