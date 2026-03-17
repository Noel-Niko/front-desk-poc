"""Integration tests for the chat API endpoint."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.main import create_app


@pytest_asyncio.fixture
async def client():
    """Create a test client for the FastAPI app."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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
