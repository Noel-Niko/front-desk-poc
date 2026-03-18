"""TDD tests for LLMService.chat_streaming() — streaming LLM with tool use.

Tests cover:
- Yields text_delta events for streamed text
- Handles tool_use → tool execution → loop back pattern
- Yields tool_call events when tools are invoked
- Yields done event with full_text, citations, tool_used, transferred, transfer_reason
- Tracks transferred/transfer_reason from transfer_to_human tool
- Maintains conversation state across the tool loop
- Pre-tool text streams before tool execution

All tests mock the Anthropic SDK — no real API calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services.llm import LLMService


def _make_text_block(text: str) -> MagicMock:
    """Create a mock TextBlock."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(name: str, tool_id: str, tool_input: dict) -> MagicMock:
    """Create a mock ToolUseBlock."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = tool_id
    block.input = tool_input
    return block


def _make_stream_context(text_chunks: list[str], final_message: MagicMock) -> AsyncMock:
    """Create a mock stream context manager that yields text chunks."""
    stream = AsyncMock()

    async def mock_text_stream():
        for chunk in text_chunks:
            yield chunk

    stream.text_stream = mock_text_stream()
    stream.get_final_message = AsyncMock(return_value=final_message)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=stream)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


def _make_final_message(stop_reason: str, content: list) -> MagicMock:
    """Create a mock final message."""
    msg = MagicMock()
    msg.stop_reason = stop_reason
    msg.content = content
    return msg


@pytest.fixture
def llm_service():
    """Create an LLMService with mocked dependencies."""
    client = MagicMock()
    # messages.stream() is a sync method that returns an async context manager
    client.messages = MagicMock()
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])  # No FAQ overrides
    handbook_index = MagicMock()
    service = LLMService(
        client=client,
        model="claude-sonnet-4-20250514",
        handbook_index=handbook_index,
        db=db,
    )
    return service, client


class TestChatStreamingTextOnly:
    """Tests for simple text responses (no tool calls)."""

    @pytest.mark.asyncio
    async def test_yields_text_deltas(self, llm_service):
        """chat_streaming should yield text_delta events for each token."""
        service, client = llm_service

        final_msg = _make_final_message("end_turn", [_make_text_block("Hello world")])
        stream_ctx = _make_stream_context(["Hello", " ", "world"], final_msg)
        client.messages.stream.return_value = stream_ctx

        events = []
        async for event in service.chat_streaming("session-1", "Hi"):
            events.append(event)

        text_deltas = [e for e in events if e["type"] == "text_delta"]
        assert len(text_deltas) == 3
        assert text_deltas[0]["text"] == "Hello"
        assert text_deltas[1]["text"] == " "
        assert text_deltas[2]["text"] == "world"

    @pytest.mark.asyncio
    async def test_yields_done_event(self, llm_service):
        """chat_streaming should yield a done event at the end."""
        service, client = llm_service

        final_msg = _make_final_message("end_turn", [_make_text_block("Hello")])
        stream_ctx = _make_stream_context(["Hello"], final_msg)
        client.messages.stream.return_value = stream_ctx

        events = []
        async for event in service.chat_streaming("session-1", "Hi"):
            events.append(event)

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1
        done = done_events[0]
        assert done["full_text"] == "Hello"
        assert done["citations"] == []
        assert done["tool_used"] is None
        assert done["transferred"] is False
        assert done["transfer_reason"] is None

    @pytest.mark.asyncio
    async def test_adds_messages_to_conversation_state(self, llm_service):
        """chat_streaming should maintain conversation history."""
        service, client = llm_service

        final_msg = _make_final_message("end_turn", [_make_text_block("Hi there")])
        stream_ctx = _make_stream_context(["Hi there"], final_msg)
        client.messages.stream.return_value = stream_ctx

        async for _ in service.chat_streaming("session-1", "Hello"):
            pass

        state = service.get_or_create_session("session-1")
        assert len(state.messages) == 2  # user + assistant
        assert state.messages[0]["role"] == "user"
        assert state.messages[0]["content"] == "Hello"
        assert state.messages[1]["role"] == "assistant"
        assert state.messages[1]["content"] == "Hi there"


class TestChatStreamingWithTools:
    """Tests for responses that involve tool calls."""

    @pytest.mark.asyncio
    async def test_handles_tool_call_and_yields_tool_event(self, llm_service):
        """When Claude calls a tool, chat_streaming should yield tool_call event."""
        service, client = llm_service

        # First call: tool_use
        tool_block = _make_tool_use_block(
            "search_handbook",
            "tool-1",
            {"query": "hours"},
        )
        first_msg = _make_final_message("tool_use", [tool_block])
        first_stream = _make_stream_context([], first_msg)

        # Second call: text response
        second_msg = _make_final_message(
            "end_turn",
            [_make_text_block("We open at 7am.")],
        )
        second_stream = _make_stream_context(["We open at 7am."], second_msg)

        client.messages.stream.side_effect = [first_stream, second_stream]

        # Mock the handbook search
        with patch.object(
            service, "_execute_tool", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = [
                {"page_number": 31, "section_title": "Hours", "text": "Open 7am-6pm"},
            ]

            events = []
            async for event in service.chat_streaming("session-1", "When do you open?"):
                events.append(event)

        tool_events = [e for e in events if e["type"] == "tool_call"]
        assert len(tool_events) == 1
        assert tool_events[0]["name"] == "search_handbook"

    @pytest.mark.asyncio
    async def test_yields_citations_from_handbook(self, llm_service):
        """Citations from search_handbook should appear in the done event."""
        service, client = llm_service

        tool_block = _make_tool_use_block(
            "search_handbook",
            "tool-1",
            {"query": "hours"},
        )
        first_msg = _make_final_message("tool_use", [tool_block])
        first_stream = _make_stream_context([], first_msg)

        second_msg = _make_final_message(
            "end_turn",
            [_make_text_block("We open at 7am (p.31).")],
        )
        second_stream = _make_stream_context(["We open at 7am (p.31)."], second_msg)

        client.messages.stream.side_effect = [first_stream, second_stream]

        with patch.object(
            service, "_execute_tool", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = [
                {
                    "page_number": 31,
                    "section_title": "Hours",
                    "text": "Open 7am-6pm Monday to Friday.",
                },
            ]

            events = []
            async for event in service.chat_streaming("session-1", "hours?"):
                events.append(event)

        done = [e for e in events if e["type"] == "done"][0]
        assert len(done["citations"]) == 1
        assert done["citations"][0]["page"] == 31
        assert done["citations"][0]["section"] == "Hours"
        assert done["tool_used"] == "search_handbook"

    @pytest.mark.asyncio
    async def test_tracks_transfer_to_human(self, llm_service):
        """transfer_to_human tool should set transferred=True in done event."""
        service, client = llm_service

        tool_block = _make_tool_use_block(
            "transfer_to_human",
            "tool-1",
            {"reason": "Billing dispute"},
        )
        first_msg = _make_final_message("tool_use", [tool_block])
        first_stream = _make_stream_context([], first_msg)

        second_msg = _make_final_message(
            "end_turn",
            [_make_text_block("Transferring you now.")],
        )
        second_stream = _make_stream_context(["Transferring you now."], second_msg)

        client.messages.stream.side_effect = [first_stream, second_stream]

        with patch.object(
            service, "_execute_tool", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = {
                "status": "Transfer initiated",
                "reason": "Billing dispute",
            }

            events = []
            async for event in service.chat_streaming(
                "session-1", "I have a billing issue"
            ):
                events.append(event)

        done = [e for e in events if e["type"] == "done"][0]
        assert done["transferred"] is True
        assert done["transfer_reason"] == "Billing dispute"
        assert done["tool_used"] == "transfer_to_human"

    @pytest.mark.asyncio
    async def test_pre_tool_text_streams_before_tool(self, llm_service):
        """Pre-tool text like 'Let me look that up' should yield text_deltas."""
        service, client = llm_service

        # First call: text + tool_use
        text_block = _make_text_block("Let me check.")
        tool_block = _make_tool_use_block(
            "search_handbook",
            "tool-1",
            {"query": "illness policy"},
        )
        first_msg = _make_final_message("tool_use", [text_block, tool_block])
        first_stream = _make_stream_context(["Let me ", "check."], first_msg)

        # Second call: final text
        second_msg = _make_final_message(
            "end_turn",
            [_make_text_block("Here's the policy.")],
        )
        second_stream = _make_stream_context(["Here's the policy."], second_msg)

        client.messages.stream.side_effect = [first_stream, second_stream]

        with patch.object(
            service, "_execute_tool", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = [
                {
                    "page_number": 43,
                    "section_title": "Illness",
                    "text": "Keep home if fever.",
                },
            ]

            events = []
            async for event in service.chat_streaming(
                "session-1", "What's the illness policy?"
            ):
                events.append(event)

        text_deltas = [e for e in events if e["type"] == "text_delta"]
        # Should have pre-tool text deltas + post-tool text deltas
        assert len(text_deltas) >= 3
        assert text_deltas[0]["text"] == "Let me "
        assert text_deltas[1]["text"] == "check."
