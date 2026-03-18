"""TDD tests for session continuity and end_session features.

Tests verify:
- Previous session lookup by security_code_used (last 7 days) returns summary
- No previous session for first-time visitor returns empty context
- Continuity context injected into system prompt
- end_session() calls Claude Haiku to summarize and updates DB
- end_session() test verifies Haiku prompt content
- previous_session_id populated when creating new session with matching security code
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.services.llm import LLMService, ConversationState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """Mock database with configurable fetch_one/fetch_all/execute."""
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=None)
    db.fetch_all = AsyncMock(return_value=[])
    db.execute = AsyncMock()
    db.insert = AsyncMock(return_value=1)
    return db


@pytest.fixture
def mock_client():
    """Mock Anthropic client."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_index():
    """Mock handbook index."""
    return MagicMock()


@pytest.fixture
def llm_service(mock_client, mock_index, mock_db):
    """LLMService with all dependencies mocked."""
    return LLMService(
        client=mock_client,
        model="claude-sonnet-4-20250514",
        handbook_index=mock_index,
        db=mock_db,
    )


# ---------------------------------------------------------------------------
# Continuity context tests
# ---------------------------------------------------------------------------


class TestContinuityContext:
    """Tests for _get_continuity_context()."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_first_time_visitor(self, llm_service, mock_db):
        """First-time visitor with no matching security code gets no context."""
        mock_db.fetch_one.return_value = None

        state = ConversationState("session-1")
        state.verified_child_id = 1
        state.verified_child_name = "Sofia Martinez"

        context = await llm_service._get_continuity_context(state)
        assert context == ""

    @pytest.mark.asyncio
    async def test_returns_summary_for_returning_visitor(self, llm_service, mock_db):
        """Returning visitor with matching security code gets previous summary."""
        # Simulate a previous session found by security code
        previous_session = {
            "id": "prev-session-1",
            "summary": "Parent asked about Sofia's meals and attendance. Sofia had a good day.",
            "security_code_used": "1234",
            "ended_at": (datetime.now() - timedelta(days=2)).isoformat(),
        }
        mock_db.fetch_one.return_value = previous_session

        state = ConversationState("session-2")
        state.session_id = "session-2"
        state.verified_child_id = 1
        state.verified_child_name = "Sofia Martinez"

        context = await llm_service._get_continuity_context(state)
        assert "Sofia" in context
        assert "meals" in context or "previous" in context.lower()

    @pytest.mark.asyncio
    async def test_ignores_sessions_older_than_7_days(self, llm_service, mock_db):
        """Sessions older than 7 days should not be returned."""
        # DB returns None because the query filters by date
        mock_db.fetch_one.return_value = None

        state = ConversationState("session-new")
        state.verified_child_id = 1

        context = await llm_service._get_continuity_context(state)
        assert context == ""

    @pytest.mark.asyncio
    async def test_context_injected_into_system_prompt(self, llm_service, mock_db):
        """Continuity context should appear in the system prompt when child is verified."""
        previous_session = {
            "id": "prev-1",
            "summary": "Parent discussed field trip permissions and pickup schedule changes.",
            "security_code_used": "5678",
            "ended_at": (datetime.now() - timedelta(days=1)).isoformat(),
        }
        # First call: FAQ overrides (empty)
        # Second call: previous session (for continuity)
        mock_db.fetch_all.return_value = []  # no FAQ overrides
        mock_db.fetch_one.return_value = previous_session

        state = ConversationState("session-new")
        state.verified_child_id = 1
        state.verified_child_name = "Sofia Martinez"

        prompt = await llm_service._build_system_prompt(state)
        assert "field trip" in prompt.lower() or "previous" in prompt.lower()


# ---------------------------------------------------------------------------
# end_session tests
# ---------------------------------------------------------------------------


class TestEndSession:
    """Tests for end_session() with Haiku summarization."""

    @pytest.mark.asyncio
    async def test_end_session_calls_haiku_to_summarize(
        self, llm_service, mock_db, mock_client
    ):
        """end_session should call Claude Haiku to generate a summary."""
        # Setup: session exists with messages
        mock_db.fetch_all.return_value = [
            {"role": "user", "content": "What are your hours?"},
            {
                "role": "assistant",
                "content": "We are open 7am-6pm Monday through Friday.",
            },
        ]

        # Mock Haiku response
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = (
            "Parent asked about center hours. Was informed of 7am-6pm M-F schedule."
        )
        mock_response.content = [mock_text_block]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        result = await llm_service.end_session("test-session-1")

        # Should have called Haiku
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "haiku" in call_kwargs["model"].lower()

        # Should return summary
        assert "summary" in result
        assert "hours" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_end_session_updates_db(self, llm_service, mock_db, mock_client):
        """end_session should update sessions.summary and sessions.ended_at."""
        mock_db.fetch_all.return_value = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Brief greeting exchange."
        mock_response.content = [mock_text_block]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        await llm_service.end_session("test-session-2")

        # Should have called execute to update the session
        mock_db.execute.assert_called_once()
        sql_call = mock_db.execute.call_args
        sql = sql_call.args[0] if sql_call.args else sql_call.kwargs.get("sql", "")
        params = (
            sql_call.args[1]
            if len(sql_call.args) > 1
            else sql_call.kwargs.get("params", ())
        )
        assert "UPDATE sessions" in sql
        assert "summary" in sql.lower()
        assert "ended_at" in sql.lower()
        assert "test-session-2" in params

    @pytest.mark.asyncio
    async def test_end_session_haiku_prompt_includes_messages(
        self, llm_service, mock_db, mock_client
    ):
        """The Haiku prompt should include the conversation messages for context."""
        messages = [
            {"role": "user", "content": "Is Sofia allergic to anything?"},
            {
                "role": "assistant",
                "content": "Sofia has a peanut allergy documented by Dr. Smith.",
            },
        ]
        mock_db.fetch_all.return_value = messages

        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Allergy inquiry for Sofia."
        mock_response.content = [mock_text_block]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        await llm_service.end_session("test-session-3")

        # Check that the Haiku call includes conversation content
        call_kwargs = mock_client.messages.create.call_args.kwargs
        messages_sent = call_kwargs["messages"]
        user_content = messages_sent[0]["content"]
        assert "Sofia" in user_content or "allergic" in user_content

    @pytest.mark.asyncio
    async def test_end_session_returns_empty_summary_when_no_messages(
        self, llm_service, mock_db, mock_client
    ):
        """If session has no messages, return empty summary without calling Haiku."""
        mock_db.fetch_all.return_value = []

        result = await llm_service.end_session("empty-session")

        mock_client.messages.create.assert_not_called()
        assert result["summary"] == ""


# ---------------------------------------------------------------------------
# previous_session_id population tests
# ---------------------------------------------------------------------------


class TestPreviousSessionId:
    """Tests for populating previous_session_id during security code verification."""

    @pytest.mark.asyncio
    async def test_previous_session_id_set_on_verification(self, llm_service, mock_db):
        """When verifying security code, should find and link to previous session."""
        # First call: find child by security code
        child_row = {
            "id": 1,
            "first_name": "Sofia",
            "last_name": "Martinez",
            "classroom": "Butterflies",
        }
        # Second call: find previous session with same security code
        prev_session_row = {"id": "prev-session-abc"}

        mock_db.fetch_one.side_effect = [child_row, prev_session_row]

        result = await llm_service.verify_security_code("new-session-1", "1234")

        assert result["verified"] is True

        # Should have called execute to update previous_session_id
        # (db.execute is called to set previous_session_id on the current session)
        update_calls = [
            c
            for c in mock_db.execute.call_args_list
            if c.args and "previous_session_id" in c.args[0]
        ]
        assert len(update_calls) == 1

    @pytest.mark.asyncio
    async def test_no_previous_session_for_first_visit(self, llm_service, mock_db):
        """First-time visitor should not get a previous_session_id."""
        child_row = {
            "id": 2,
            "first_name": "Liam",
            "last_name": "Chen",
            "classroom": "Ladybugs",
        }
        # First call: find child; Second call: no previous session
        mock_db.fetch_one.side_effect = [child_row, None]

        result = await llm_service.verify_security_code("first-visit", "5678")

        assert result["verified"] is True
        # Should NOT call execute for previous_session_id
        update_calls = [
            c
            for c in mock_db.execute.call_args_list
            if c.args and "previous_session_id" in str(c.args)
        ]
        assert len(update_calls) == 0
