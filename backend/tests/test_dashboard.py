"""Tests for the operator dashboard API."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.config import Settings
from backend.app.db.database import Database
from backend.app.db.seed import seed_database
from backend.app.dashboard.server import create_app


@pytest_asyncio.fixture
async def client(tmp_path):
    """Create a test client for the dashboard app."""
    db_path = str(tmp_path / "test_dashboard.db")

    app = create_app()

    # Manually initialize state (lifespan not triggered by httpx)
    db = Database(db_path)
    await db.connect()
    await seed_database(db)
    app.state.db = db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await db.close()


class TestDashboardHTML:
    @pytest.mark.asyncio
    async def test_root_returns_html(self, client: AsyncClient) -> None:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Operator Dashboard" in resp.text


class TestSessionsAPI:
    @pytest.mark.asyncio
    async def test_list_sessions(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Seed data has at least 1 session
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_session_detail(self, client: AsyncClient) -> None:
        # Get sessions first
        sessions_resp = await client.get("/api/sessions")
        sessions = sessions_resp.json()
        session_id = sessions[0]["id"]

        resp = await client.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == session_id
        assert "messages" in data

    @pytest.mark.asyncio
    async def test_session_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sessions/nonexistent-id")
        assert resp.status_code == 404


class TestStatsAPI:
    @pytest.mark.asyncio
    async def test_stats_returns_kpi_data(self, client: AsyncClient) -> None:
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sessions" in data
        assert "total_messages" in data
        assert "transfer_rate" in data


class TestStrugglesAPI:
    @pytest.mark.asyncio
    async def test_struggles_returns_list(self, client: AsyncClient) -> None:
        resp = await client.get("/api/struggles")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestFAQOverridesAPI:
    @pytest.mark.asyncio
    async def test_list_faq_overrides(self, client: AsyncClient) -> None:
        resp = await client.get("/api/faq-overrides")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Seed data has 2 FAQ overrides
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_create_faq_override(self, client: AsyncClient) -> None:
        resp = await client.post("/api/faq-overrides", json={
            "question_pattern": "What is your phone number?",
            "answer": "Our phone number is (505) 555-0100.",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] is not None
        assert data["question_pattern"] == "What is your phone number?"

    @pytest.mark.asyncio
    async def test_update_faq_override(self, client: AsyncClient) -> None:
        # Create first
        create_resp = await client.post("/api/faq-overrides", json={
            "question_pattern": "Test question",
            "answer": "Test answer",
        })
        override_id = create_resp.json()["id"]

        # Update
        resp = await client.put(f"/api/faq-overrides/{override_id}", json={
            "answer": "Updated answer",
        })
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Updated answer"

    @pytest.mark.asyncio
    async def test_delete_faq_override(self, client: AsyncClient) -> None:
        # Create first
        create_resp = await client.post("/api/faq-overrides", json={
            "question_pattern": "To be deleted",
            "answer": "Delete me",
        })
        override_id = create_resp.json()["id"]

        # Delete
        resp = await client.delete(f"/api/faq-overrides/{override_id}")
        assert resp.status_code == 200

        # Verify gone
        list_resp = await client.get("/api/faq-overrides")
        ids = [o["id"] for o in list_resp.json()]
        assert override_id not in ids


class TestTourRequestsAPI:
    @pytest.mark.asyncio
    async def test_list_tour_requests(self, client: AsyncClient) -> None:
        resp = await client.get("/api/tour-requests")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
