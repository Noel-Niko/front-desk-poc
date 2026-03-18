"""Tests for the operator dashboard API."""

import json
from datetime import datetime, timedelta

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
        yield ac, db

    await db.close()


async def _seed_rated_sessions(db: Database) -> None:
    """Insert sessions with ratings for testing analytics."""
    now = datetime.now()
    sessions = [
        ("rated-1", (now - timedelta(days=1)).isoformat(), 5, "Excellent!", None),
        ("rated-2", (now - timedelta(days=2)).isoformat(), 4, "Good", None),
        ("rated-3", (now - timedelta(days=3)).isoformat(), 2, "Slow response", None),
        ("rated-4", (now - timedelta(days=4)).isoformat(), 1, "Did not help", None),
        ("rated-5", (now - timedelta(days=5)).isoformat(), 3, None, None),
    ]
    for sid, started, rating, feedback, _ in sessions:
        await db.insert(
            """INSERT INTO sessions (id, started_at, input_mode, rating, rating_feedback, ended_at)
               VALUES (?, ?, 'text', ?, ?, ?)""",
            (sid, started, rating, feedback, started),
        )
    # Add messages with citations to rated-1
    citations = json.dumps([{"page": 31, "section": "Hours", "text": "Open 7am-6pm"}])
    await db.insert(
        "INSERT INTO messages (session_id, role, content, citations, tool_used, timestamp) VALUES (?, 'assistant', ?, ?, 'search_handbook', ?)",
        ("rated-1", "We are open 7am to 6pm.", citations, now.isoformat()),
    )
    citations2 = json.dumps([{"page": 31, "section": "Hours", "text": "Open 7am-6pm"}, {"page": 43, "section": "Illness", "text": "Fever policy"}])
    await db.insert(
        "INSERT INTO messages (session_id, role, content, citations, tool_used, timestamp) VALUES (?, 'assistant', ?, ?, 'search_handbook', ?)",
        ("rated-2", "Hours are 7am-6pm. Illness policy is on page 43.", citations2, now.isoformat()),
    )


class TestDashboardHTML:
    @pytest.mark.asyncio
    async def test_root_returns_html(self, client) -> None:
        ac, _ = client
        resp = await ac.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Operator Dashboard" in resp.text


class TestSessionsAPI:
    @pytest.mark.asyncio
    async def test_list_sessions(self, client) -> None:
        ac, _ = client
        resp = await ac.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Seed data has at least 1 session
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_session_detail(self, client) -> None:
        ac, _ = client
        # Get sessions first
        sessions_resp = await ac.get("/api/sessions")
        sessions = sessions_resp.json()
        session_id = sessions[0]["id"]

        resp = await ac.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == session_id
        assert "messages" in data

    @pytest.mark.asyncio
    async def test_session_not_found(self, client) -> None:
        ac, _ = client
        resp = await ac.get("/api/sessions/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_sessions_filter_by_min_rating(self, client) -> None:
        ac, db = client
        await _seed_rated_sessions(db)

        resp = await ac.get("/api/sessions?min_rating=4")
        assert resp.status_code == 200
        data = resp.json()
        assert all(s.get("rating", 0) >= 4 for s in data if s.get("rating") is not None)

    @pytest.mark.asyncio
    async def test_list_sessions_filter_transferred_only(self, client) -> None:
        ac, _ = client
        resp = await ac.get("/api/sessions?transferred_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["transferred_to_human"] == 1 for s in data)


class TestStatsAPI:
    @pytest.mark.asyncio
    async def test_stats_returns_kpi_data(self, client) -> None:
        ac, _ = client
        resp = await ac.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sessions" in data
        assert "total_messages" in data
        assert "transfer_rate" in data

    @pytest.mark.asyncio
    async def test_stats_includes_rating_data(self, client) -> None:
        ac, db = client
        await _seed_rated_sessions(db)

        resp = await ac.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "avg_rating" in data
        assert "rating_count" in data
        assert data["rating_count"] >= 5
        assert 1.0 <= data["avg_rating"] <= 5.0


class TestStrugglesAPI:
    @pytest.mark.asyncio
    async def test_struggles_returns_list(self, client) -> None:
        ac, _ = client
        resp = await ac.get("/api/struggles")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestRatingDistributionAPI:
    @pytest.mark.asyncio
    async def test_rating_distribution(self, client) -> None:
        ac, db = client
        await _seed_rated_sessions(db)

        resp = await ac.get("/api/rating-distribution")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should have entries for ratings 1-5
        ratings = {d["rating"] for d in data}
        assert 1 in ratings
        assert 5 in ratings


class TestCitationFrequencyAPI:
    @pytest.mark.asyncio
    async def test_citation_frequency(self, client) -> None:
        ac, db = client
        await _seed_rated_sessions(db)

        resp = await ac.get("/api/citation-frequency")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should have at least page 31 (from seeded data)
        pages = {d["page"] for d in data}
        assert 31 in pages


class TestLowRatingSessionsAPI:
    @pytest.mark.asyncio
    async def test_low_rating_sessions(self, client) -> None:
        ac, db = client
        await _seed_rated_sessions(db)

        resp = await ac.get("/api/low-rating-sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should include sessions with rating <= 2
        assert len(data) >= 2
        assert all(s["rating"] <= 2 for s in data)


class TestFAQOverridesAPI:
    @pytest.mark.asyncio
    async def test_list_faq_overrides(self, client) -> None:
        ac, _ = client
        resp = await ac.get("/api/faq-overrides")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Seed data has 2 FAQ overrides
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_create_faq_override(self, client) -> None:
        ac, _ = client
        resp = await ac.post("/api/faq-overrides", json={
            "question_pattern": "What is your phone number?",
            "answer": "Our phone number is (505) 555-0100.",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] is not None
        assert data["question_pattern"] == "What is your phone number?"

    @pytest.mark.asyncio
    async def test_update_faq_override(self, client) -> None:
        ac, _ = client
        # Create first
        create_resp = await ac.post("/api/faq-overrides", json={
            "question_pattern": "Test question",
            "answer": "Test answer",
        })
        override_id = create_resp.json()["id"]

        # Update
        resp = await ac.put(f"/api/faq-overrides/{override_id}", json={
            "answer": "Updated answer",
        })
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Updated answer"

    @pytest.mark.asyncio
    async def test_delete_faq_override(self, client) -> None:
        ac, _ = client
        # Create first
        create_resp = await ac.post("/api/faq-overrides", json={
            "question_pattern": "To be deleted",
            "answer": "Delete me",
        })
        override_id = create_resp.json()["id"]

        # Delete
        resp = await ac.delete(f"/api/faq-overrides/{override_id}")
        assert resp.status_code == 200

        # Verify gone
        list_resp = await ac.get("/api/faq-overrides")
        ids = [o["id"] for o in list_resp.json()]
        assert override_id not in ids


class TestTourRequestsAPI:
    @pytest.mark.asyncio
    async def test_list_tour_requests(self, client) -> None:
        ac, _ = client
        resp = await ac.get("/api/tour-requests")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
