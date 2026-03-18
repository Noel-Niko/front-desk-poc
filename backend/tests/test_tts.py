"""TDD tests for TTS pure-logic components.

Tests cover:
- strip_markdown: removes markdown formatting for natural TTS speech
- split_into_sentences: splits text on sentence boundaries, preserves abbreviations
- CartesiaTTSService: synthesize + read_response protocol (tts_start → binary → tts_end)
- Graceful no-op when API key is empty
- Empty text returns immediately (no Cartesia call)

These tests do NOT depend on the Cartesia SDK — all external calls are mocked.
SDK-specific integration tests will be added after docs/cartesia_ws_research.md.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# strip_markdown tests
# ---------------------------------------------------------------------------

class TestStripMarkdown:
    """strip_markdown removes formatting for clean TTS input."""

    def test_removes_bold(self):
        from backend.app.services.cartesia_tts import strip_markdown
        assert strip_markdown("This is **bold** text") == "This is bold text"

    def test_removes_italic(self):
        from backend.app.services.cartesia_tts import strip_markdown
        assert strip_markdown("This is *italic* text") == "This is italic text"

    def test_removes_headers(self):
        from backend.app.services.cartesia_tts import strip_markdown
        result = strip_markdown("## Section Title\nSome content")
        assert "##" not in result
        assert "Section Title" in result
        assert "Some content" in result

    def test_removes_links(self):
        from backend.app.services.cartesia_tts import strip_markdown
        assert strip_markdown("Visit [our site](https://example.com) today") == "Visit our site today"

    def test_removes_code_blocks(self):
        from backend.app.services.cartesia_tts import strip_markdown
        result = strip_markdown("Before\n```python\ncode here\n```\nAfter")
        assert "```" not in result
        assert "code here" not in result
        assert "Before" in result
        assert "After" in result

    def test_removes_inline_code(self):
        from backend.app.services.cartesia_tts import strip_markdown
        assert strip_markdown("Use `pip install` to install") == "Use pip install to install"

    def test_removes_list_markers(self):
        from backend.app.services.cartesia_tts import strip_markdown
        result = strip_markdown("- Item one\n- Item two\n1. Numbered")
        assert "- " not in result
        assert "1. " not in result
        assert "Item one" in result
        assert "Numbered" in result

    def test_empty_string_returns_empty(self):
        from backend.app.services.cartesia_tts import strip_markdown
        assert strip_markdown("") == ""

    def test_none_returns_empty(self):
        from backend.app.services.cartesia_tts import strip_markdown
        assert strip_markdown(None) == ""

    def test_plain_text_unchanged(self):
        from backend.app.services.cartesia_tts import strip_markdown
        text = "Hello, how can I help you today?"
        assert strip_markdown(text) == text

    def test_removes_horizontal_rules(self):
        from backend.app.services.cartesia_tts import strip_markdown
        result = strip_markdown("Above\n---\nBelow")
        assert "---" not in result


# ---------------------------------------------------------------------------
# split_into_sentences tests
# ---------------------------------------------------------------------------

class TestSplitIntoSentences:
    """split_into_sentences splits on . ? ! boundaries."""

    def test_splits_on_period(self):
        from backend.app.services.cartesia_tts import split_into_sentences
        result = split_into_sentences("First sentence. Second sentence.")
        assert result == ["First sentence.", "Second sentence."]

    def test_splits_on_question_mark(self):
        from backend.app.services.cartesia_tts import split_into_sentences
        result = split_into_sentences("How are you? I am fine.")
        assert result == ["How are you?", "I am fine."]

    def test_splits_on_exclamation(self):
        from backend.app.services.cartesia_tts import split_into_sentences
        result = split_into_sentences("Great news! We are open.")
        assert result == ["Great news!", "We are open."]

    def test_preserves_abbreviation_dr(self):
        from backend.app.services.cartesia_tts import split_into_sentences
        result = split_into_sentences("Dr. Smith is available. Call now.")
        assert result == ["Dr. Smith is available.", "Call now."]

    def test_preserves_abbreviation_mrs(self):
        from backend.app.services.cartesia_tts import split_into_sentences
        result = split_into_sentences("Mrs. Jones called. She left a message.")
        assert result == ["Mrs. Jones called.", "She left a message."]

    def test_preserves_abbreviation_mr(self):
        from backend.app.services.cartesia_tts import split_into_sentences
        result = split_into_sentences("Mr. Brown will arrive. He is expected at noon.")
        assert result == ["Mr. Brown will arrive.", "He is expected at noon."]

    def test_empty_string_returns_empty_list(self):
        from backend.app.services.cartesia_tts import split_into_sentences
        assert split_into_sentences("") == []

    def test_single_sentence_no_split(self):
        from backend.app.services.cartesia_tts import split_into_sentences
        result = split_into_sentences("Just one sentence.")
        assert result == ["Just one sentence."]

    def test_handles_ellipsis(self):
        from backend.app.services.cartesia_tts import split_into_sentences
        result = split_into_sentences("Well... let me think. Okay sure.")
        assert len(result) == 2
        assert "Well... let me think." in result[0]

    def test_handles_newlines_as_boundaries(self):
        from backend.app.services.cartesia_tts import split_into_sentences
        result = split_into_sentences("Line one.\nLine two.")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# CartesiaTTSService tests
# ---------------------------------------------------------------------------

class TestCartesiaTTSService:
    """Tests for CartesiaTTSService with mocked Cartesia SDK."""

    @pytest.mark.asyncio
    async def test_no_op_when_api_key_empty(self):
        """Service should be a no-op when initialized without API key."""
        from backend.app.services.cartesia_tts import CartesiaTTSService
        service = CartesiaTTSService(api_key="", voice_id="test-voice")
        ws = AsyncMock()
        # Should return without sending anything
        await service.read_response("Hello world", ws)
        ws.send_json.assert_not_called()
        ws.send_bytes.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_op_when_text_empty(self):
        """Empty text should return immediately without calling Cartesia."""
        from backend.app.services.cartesia_tts import CartesiaTTSService
        service = CartesiaTTSService(api_key="test-key", voice_id="test-voice")
        ws = AsyncMock()
        await service.read_response("", ws)
        ws.send_json.assert_not_called()
        ws.send_bytes.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_op_when_whitespace_only(self):
        """Whitespace-only text should return immediately."""
        from backend.app.services.cartesia_tts import CartesiaTTSService
        service = CartesiaTTSService(api_key="test-key", voice_id="test-voice")
        ws = AsyncMock()
        await service.read_response("   \n  ", ws)
        ws.send_json.assert_not_called()
        ws.send_bytes.assert_not_called()

    @pytest.mark.asyncio
    async def test_read_response_sends_tts_start_and_tts_end(self):
        """read_response should send tts_start JSON, binary audio, then tts_end JSON."""
        from backend.app.services.cartesia_tts import CartesiaTTSService

        service = CartesiaTTSService(api_key="test-key", voice_id="test-voice")
        ws = AsyncMock()

        # Mock the internal synthesize method to return fake audio bytes
        fake_audio = b"\x00\x01" * 100
        service._synthesize_sentence = AsyncMock(return_value=fake_audio)

        await service.read_response("Hello there.", ws)

        # First call should be tts_start
        calls = ws.send_json.call_args_list
        assert calls[0].args[0] == {"type": "tts_start"}
        # Last call should be tts_end
        assert calls[-1].args[0] == {"type": "tts_end"}
        # Should have sent binary audio
        ws.send_bytes.assert_called()

    @pytest.mark.asyncio
    async def test_read_response_sends_binary_frames(self):
        """Audio should be sent as raw binary WebSocket frames, not base64 JSON."""
        from backend.app.services.cartesia_tts import CartesiaTTSService

        service = CartesiaTTSService(api_key="test-key", voice_id="test-voice")
        ws = AsyncMock()

        fake_audio = b"\x00\x01" * 100
        service._synthesize_sentence = AsyncMock(return_value=fake_audio)

        await service.read_response("One sentence.", ws)

        # Binary frames sent via send_bytes, not send_json
        ws.send_bytes.assert_called_with(fake_audio)

    @pytest.mark.asyncio
    async def test_read_response_splits_into_sentences(self):
        """Multiple sentences should each be synthesized separately."""
        from backend.app.services.cartesia_tts import CartesiaTTSService

        service = CartesiaTTSService(api_key="test-key", voice_id="test-voice")
        ws = AsyncMock()

        fake_audio = b"\x00\x01" * 50
        service._synthesize_sentence = AsyncMock(return_value=fake_audio)

        await service.read_response("First sentence. Second sentence. Third one!", ws)

        # Should have synthesized 3 sentences
        assert service._synthesize_sentence.call_count == 3

    @pytest.mark.asyncio
    async def test_read_response_strips_markdown_before_splitting(self):
        """Markdown should be stripped before sentence splitting."""
        from backend.app.services.cartesia_tts import CartesiaTTSService

        service = CartesiaTTSService(api_key="test-key", voice_id="test-voice")
        ws = AsyncMock()

        fake_audio = b"\x00\x01" * 50
        service._synthesize_sentence = AsyncMock(return_value=fake_audio)

        await service.read_response("**Bold text.** *Italic text.*", ws)

        # Check that synthesized text doesn't contain markdown
        for call in service._synthesize_sentence.call_args_list:
            text_arg = call.args[0] if call.args else call.kwargs.get("text", "")
            assert "**" not in text_arg
            assert "*" not in text_arg or text_arg.count("*") == 0

    @pytest.mark.asyncio
    async def test_read_response_passes_speed_param(self):
        """Speed parameter should be forwarded to synthesis."""
        from backend.app.services.cartesia_tts import CartesiaTTSService

        service = CartesiaTTSService(api_key="test-key", voice_id="test-voice")
        ws = AsyncMock()

        fake_audio = b"\x00\x01" * 50
        service._synthesize_sentence = AsyncMock(return_value=fake_audio)

        await service.read_response("Hello.", ws, speed="fast")

        service._synthesize_sentence.call_args_list[0]
        # Speed should be passed through
        call_kwargs = service._synthesize_sentence.call_args
        assert call_kwargs.kwargs.get("speed") == "fast" or (len(call_kwargs.args) > 1 and call_kwargs.args[1] == "fast")

    @pytest.mark.asyncio
    async def test_read_response_error_does_not_raise(self):
        """TTS errors should be logged, not raised — text response already sent."""
        from backend.app.services.cartesia_tts import CartesiaTTSService

        service = CartesiaTTSService(api_key="test-key", voice_id="test-voice")
        ws = AsyncMock()

        service._synthesize_sentence = AsyncMock(side_effect=Exception("Cartesia down"))

        # Should NOT raise
        await service.read_response("Hello.", ws)

    @pytest.mark.asyncio
    async def test_close_is_safe_when_not_connected(self):
        """close() should be safe to call even if never connected."""
        from backend.app.services.cartesia_tts import CartesiaTTSService
        service = CartesiaTTSService(api_key="test-key", voice_id="test-voice")
        await service.close()  # Should not raise
