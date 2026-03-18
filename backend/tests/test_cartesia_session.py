"""TDD tests for CartesiaSession — Cartesia WebSocket TTS session manager.

Tests cover:
- Connection lifecycle (connect, close)
- Context creation for utterances (start_utterance)
- Sentence pushing (push_sentence)
- End-of-utterance signaling (finish_utterance)
- Audio chunk forwarding via callback
- Barge-in cancellation (cancel_utterance)
- Graceful handling when not connected
- Error resilience

All tests mock the Cartesia SDK — no real API calls.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCartesiaSessionConnect:
    """Connection lifecycle tests."""

    @pytest.mark.asyncio
    async def test_connect_creates_websocket(self):
        """connect() should open a Cartesia WebSocket connection."""
        from backend.app.services.cartesia_session import CartesiaSession

        mock_client = MagicMock()
        mock_ws_connection = AsyncMock()
        mock_ws_ctx = AsyncMock()
        mock_ws_ctx.__aenter__ = AsyncMock(return_value=mock_ws_connection)
        mock_ws_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_client.tts.websocket_connect.return_value = mock_ws_ctx

        with patch("backend.app.services.cartesia_session.AsyncCartesia", return_value=mock_client):
            session = CartesiaSession(
                api_key="test-key",
                voice_id="test-voice",
            )
            await session.connect()

            mock_client.tts.websocket_connect.assert_called_once()
            await session.close()

    @pytest.mark.asyncio
    async def test_connect_stores_connection(self):
        """After connect(), the session should have an active connection."""
        from backend.app.services.cartesia_session import CartesiaSession

        mock_client = MagicMock()
        mock_ws_connection = AsyncMock()
        mock_ws_ctx = AsyncMock()
        mock_ws_ctx.__aenter__ = AsyncMock(return_value=mock_ws_connection)
        mock_ws_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_client.tts.websocket_connect.return_value = mock_ws_ctx

        with patch("backend.app.services.cartesia_session.AsyncCartesia", return_value=mock_client):
            session = CartesiaSession(api_key="test-key", voice_id="test-voice")
            await session.connect()
            assert session._connection is not None
            await session.close()

    @pytest.mark.asyncio
    async def test_close_when_not_connected_is_safe(self):
        """close() should be safe to call even if never connected."""
        from backend.app.services.cartesia_session import CartesiaSession

        with patch("backend.app.services.cartesia_session.AsyncCartesia"):
            session = CartesiaSession(api_key="test-key", voice_id="test-voice")
            await session.close()  # Should not raise


class TestCartesiaSessionUtterance:
    """Utterance lifecycle: start → push sentences → finish."""

    @pytest.fixture
    def connected_session(self):
        """Fixture that provides a connected CartesiaSession with mocked SDK."""
        from backend.app.services.cartesia_session import CartesiaSession

        mock_client = MagicMock()
        mock_ws_connection = MagicMock()  # Regular MagicMock — context() is sync

        # Mock the context object returned by connection.context()
        mock_ctx = MagicMock()
        mock_ctx.push = AsyncMock()
        mock_ctx.no_more_inputs = AsyncMock()

        async def mock_receive():
            return
            yield  # Make it an async generator that yields nothing

        mock_ctx.receive = mock_receive
        mock_ws_connection.context.return_value = mock_ctx

        mock_ws_ctx = AsyncMock()
        mock_ws_ctx.__aenter__ = AsyncMock(return_value=mock_ws_connection)
        mock_ws_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_client.tts.websocket_connect.return_value = mock_ws_ctx

        return {
            "client": mock_client,
            "connection": mock_ws_connection,
            "ctx": mock_ctx,
            "session_class": CartesiaSession,
        }

    @pytest.mark.asyncio
    async def test_start_utterance_creates_context(self, connected_session):
        """start_utterance() should create a Cartesia context."""
        mocks = connected_session
        on_audio = AsyncMock()

        with patch("backend.app.services.cartesia_session.AsyncCartesia", return_value=mocks["client"]):
            session = mocks["session_class"](api_key="test-key", voice_id="test-voice")
            await session.connect()
            await session.start_utterance(on_audio)

            mocks["connection"].context.assert_called_once()
            # Verify model_id and voice are passed
            call_kwargs = mocks["connection"].context.call_args
            assert call_kwargs.kwargs.get("model_id") == "sonic-3"
            await session.cancel_utterance()
            await session.close()

    @pytest.mark.asyncio
    async def test_push_sentence_calls_ctx_push(self, connected_session):
        """push_sentence() should call await ctx.push() with the text."""
        mocks = connected_session
        on_audio = AsyncMock()

        with patch("backend.app.services.cartesia_session.AsyncCartesia", return_value=mocks["client"]):
            session = mocks["session_class"](api_key="test-key", voice_id="test-voice")
            await session.connect()
            await session.start_utterance(on_audio)

            await session.push_sentence("Hello world.")

            mocks["ctx"].push.assert_awaited_once_with("Hello world.")
            await session.cancel_utterance()
            await session.close()

    @pytest.mark.asyncio
    async def test_finish_utterance_calls_no_more_inputs(self, connected_session):
        """finish_utterance() should call await ctx.no_more_inputs()."""
        mocks = connected_session
        on_audio = AsyncMock()

        with patch("backend.app.services.cartesia_session.AsyncCartesia", return_value=mocks["client"]):
            session = mocks["session_class"](api_key="test-key", voice_id="test-voice")
            await session.connect()
            await session.start_utterance(on_audio)

            await session.finish_utterance()

            mocks["ctx"].no_more_inputs.assert_awaited_once()
            await session.close()

    @pytest.mark.asyncio
    async def test_push_sentence_without_start_is_noop(self, connected_session):
        """push_sentence() without start_utterance() should be a safe no-op."""
        mocks = connected_session

        with patch("backend.app.services.cartesia_session.AsyncCartesia", return_value=mocks["client"]):
            session = mocks["session_class"](api_key="test-key", voice_id="test-voice")
            await session.connect()
            await session.push_sentence("Hello.")  # No start_utterance — should not raise
            await session.close()


class TestCartesiaSessionAudioForwarding:
    """Audio chunk forwarding via callback."""

    @pytest.mark.asyncio
    async def test_audio_chunks_forwarded_via_callback(self):
        """Audio chunks from ctx.receive() should be forwarded via on_audio callback."""
        from backend.app.services.cartesia_session import CartesiaSession

        mock_client = MagicMock()
        mock_ws_connection = MagicMock()  # Regular — context() is sync

        # Create mock audio chunks
        chunk1 = MagicMock()
        chunk1.audio = b"\x00\x01" * 100

        chunk2 = MagicMock()
        chunk2.audio = b"\x02\x03" * 100

        done_chunk = MagicMock()
        done_chunk.audio = None

        mock_ctx = MagicMock()
        mock_ctx.push = AsyncMock()
        mock_ctx.no_more_inputs = AsyncMock()

        async def mock_receive():
            yield chunk1
            yield chunk2
            yield done_chunk

        mock_ctx.receive = mock_receive
        mock_ws_connection.context.return_value = mock_ctx

        mock_ws_ctx = AsyncMock()
        mock_ws_ctx.__aenter__ = AsyncMock(return_value=mock_ws_connection)
        mock_ws_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_client.tts.websocket_connect.return_value = mock_ws_ctx

        on_audio = AsyncMock()

        with patch("backend.app.services.cartesia_session.AsyncCartesia", return_value=mock_client):
            session = CartesiaSession(api_key="test-key", voice_id="test-voice")
            await session.connect()
            await session.start_utterance(on_audio)

            # Push a sentence and finish to trigger receive loop
            await session.push_sentence("Hello.")
            await session.finish_utterance()

            # Callback should have been called with audio bytes
            assert on_audio.call_count == 2
            on_audio.assert_any_await(chunk1.audio)
            on_audio.assert_any_await(chunk2.audio)
            await session.close()


class TestCartesiaSessionBargeIn:
    """Barge-in cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_utterance_stops_receive(self):
        """cancel_utterance() should stop the receive loop."""
        from backend.app.services.cartesia_session import CartesiaSession

        mock_client = MagicMock()
        mock_ws_connection = MagicMock()  # Regular — context() is sync

        # Create a receive that blocks forever
        mock_ctx = MagicMock()
        mock_ctx.push = AsyncMock()
        mock_ctx.no_more_inputs = AsyncMock()

        blocking_event = asyncio.Event()

        async def mock_receive_blocking():
            yield MagicMock(audio=b"\x00\x01" * 10)
            await blocking_event.wait()  # Block forever

        mock_ctx.receive = mock_receive_blocking
        mock_ws_connection.context.return_value = mock_ctx

        mock_ws_ctx = AsyncMock()
        mock_ws_ctx.__aenter__ = AsyncMock(return_value=mock_ws_connection)
        mock_ws_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_client.tts.websocket_connect.return_value = mock_ws_ctx

        on_audio = AsyncMock()

        with patch("backend.app.services.cartesia_session.AsyncCartesia", return_value=mock_client):
            session = CartesiaSession(api_key="test-key", voice_id="test-voice")
            await session.connect()
            await session.start_utterance(on_audio)

            # Give the receive loop a moment to start
            await asyncio.sleep(0.02)

            # Cancel should not hang
            await session.cancel_utterance()

            # After cancel, context should be cleared
            assert session._current_ctx is None
            await session.close()

    @pytest.mark.asyncio
    async def test_cancel_utterance_when_no_utterance(self):
        """cancel_utterance() without an active utterance should be safe."""
        from backend.app.services.cartesia_session import CartesiaSession

        mock_client = MagicMock()
        mock_ws_connection = MagicMock()
        mock_ws_ctx = AsyncMock()
        mock_ws_ctx.__aenter__ = AsyncMock(return_value=mock_ws_connection)
        mock_ws_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_client.tts.websocket_connect.return_value = mock_ws_ctx

        with patch("backend.app.services.cartesia_session.AsyncCartesia", return_value=mock_client):
            session = CartesiaSession(api_key="test-key", voice_id="test-voice")
            await session.connect()
            await session.cancel_utterance()  # Should not raise
            await session.close()


class TestCartesiaSessionNoApiKey:
    """Behavior when no API key is provided."""

    @pytest.mark.asyncio
    async def test_no_api_key_connect_is_noop(self):
        """connect() with empty API key should be a no-op."""
        from backend.app.services.cartesia_session import CartesiaSession

        session = CartesiaSession(api_key="", voice_id="test-voice")
        await session.connect()
        assert session._connection is None
        await session.close()

    @pytest.mark.asyncio
    async def test_no_api_key_push_is_noop(self):
        """push_sentence() with no API key should be a safe no-op."""
        from backend.app.services.cartesia_session import CartesiaSession

        session = CartesiaSession(api_key="", voice_id="test-voice")
        await session.push_sentence("Hello.")  # Should not raise

    @pytest.mark.asyncio
    async def test_no_api_key_start_utterance_is_noop(self):
        """start_utterance() with no API key should be a safe no-op."""
        from backend.app.services.cartesia_session import CartesiaSession

        session = CartesiaSession(api_key="", voice_id="test-voice")
        on_audio = AsyncMock()
        await session.start_utterance(on_audio)  # Should not raise
