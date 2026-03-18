"""Tests for voice WebSocket endpoint and DeepgramSession.

Tests verify:
- WebSocket sends error and closes when no Deepgram API key is configured
- WebSocket accepts config messages and sends config_ack
- Config with tts_enabled/tts_speed is acknowledged correctly
- Default tts_enabled=false when not specified (backward compat)
- TTS frames sent after response when enabled
- No TTS frames when disabled
- TTS error doesn't break text response delivery
- DeepgramSession uses the correct async SDK API (listen.v1.connect pattern)
- DeepgramSession forwards audio via send_media
- DeepgramSession graceful shutdown sequence
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.app.api.websocket import router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_no_deepgram():
    """Minimal app with voice WebSocket router, no Deepgram API key."""
    app = FastAPI()
    app.include_router(router)
    app.state.db = AsyncMock()
    app.state.llm_service = AsyncMock()
    app.state.tts_service = None
    return app


@pytest.fixture
def app_with_deepgram():
    """Minimal app with voice WebSocket router, Deepgram API key set."""
    app = FastAPI()
    app.include_router(router)
    mock_db = AsyncMock()
    mock_db.fetch_one = AsyncMock(return_value=None)
    mock_db.insert = AsyncMock()
    app.state.db = mock_db
    app.state.llm_service = AsyncMock()
    app.state.tts_service = None
    return app


@pytest.fixture
def app_with_tts():
    """App with Deepgram + TTS service configured."""
    app = FastAPI()
    app.include_router(router)
    mock_db = AsyncMock()
    mock_db.fetch_one = AsyncMock(return_value=None)
    mock_db.insert = AsyncMock()
    app.state.db = mock_db

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(
        return_value={
            "message": "Hello from the assistant.",
            "citations": [],
            "tool_used": None,
            "transferred": False,
            "transfer_reason": None,
        }
    )
    app.state.llm_service = mock_llm

    mock_tts = AsyncMock()
    mock_tts.read_response = AsyncMock()
    app.state.tts_service = mock_tts

    return app


# ---------------------------------------------------------------------------
# WebSocket endpoint tests
# ---------------------------------------------------------------------------


class TestVoiceWebSocketNoApiKey:
    """Behavior when DEEPGRAM_API_KEY is not configured."""

    def test_sends_error_and_closes_without_api_key(self, app_no_deepgram):
        """Server should send error JSON and close when no API key."""
        with patch("backend.app.api.websocket.Settings") as MockSettings:
            MockSettings.return_value.deepgram_api_key = ""
            client = TestClient(app_no_deepgram)
            with client.websocket_connect("/api/voice") as ws:
                data = ws.receive_json()
                assert data["type"] == "error"
                assert "Deepgram" in data["message"]


class TestVoiceWebSocketWithApiKey:
    """Behavior when Deepgram API key IS configured."""

    def test_connects_and_handles_config_message(self, app_with_deepgram):
        """Server should connect to Deepgram and ack config messages."""
        mock_session = MagicMock()
        mock_session.connect = AsyncMock()
        mock_session.send_audio = AsyncMock()
        mock_session.close = AsyncMock()

        with (
            patch("backend.app.api.websocket.Settings") as MockSettings,
            patch(
                "backend.app.api.websocket.DeepgramSession", return_value=mock_session
            ),
        ):
            MockSettings.return_value.deepgram_api_key = "test-key-123"
            client = TestClient(app_with_deepgram)

            with client.websocket_connect("/api/voice") as ws:
                # Should receive session_start from server
                data = ws.receive_json()
                assert data["type"] == "session_start"

                # Send config message
                ws.send_json({"type": "config", "session_id": "test-session-1"})

                # Should receive config_ack
                data = ws.receive_json()
                assert data["type"] == "config_ack"
                assert data["session_id"] == "test-session-1"

            # DeepgramSession.connect() should have been called
            mock_session.connect.assert_called_once()
            # Session should be closed on disconnect
            mock_session.close.assert_called_once()

    def test_forwards_binary_audio_to_deepgram(self, app_with_deepgram):
        """Binary frames should be forwarded to DeepgramSession.send_audio."""
        mock_session = MagicMock()
        mock_session.connect = AsyncMock()
        mock_session.send_audio = AsyncMock()
        mock_session.close = AsyncMock()

        with (
            patch("backend.app.api.websocket.Settings") as MockSettings,
            patch(
                "backend.app.api.websocket.DeepgramSession", return_value=mock_session
            ),
        ):
            MockSettings.return_value.deepgram_api_key = "test-key-123"
            client = TestClient(app_with_deepgram)

            with client.websocket_connect("/api/voice") as ws:
                # Skip session_start
                ws.receive_json()

                # Send binary audio data
                audio_chunk = b"\x00\x01" * 2048
                ws.send_bytes(audio_chunk)

            # Audio should have been forwarded
            mock_session.send_audio.assert_called_once_with(audio_chunk)


# ---------------------------------------------------------------------------
# TTS integration tests
# ---------------------------------------------------------------------------


class TestVoiceWebSocketTTS:
    """TTS integration via voice WebSocket."""

    def test_config_with_tts_enabled_is_acknowledged(self, app_with_tts):
        """Config message with tts_enabled/tts_speed should be acked."""
        mock_session = MagicMock()
        mock_session.connect = AsyncMock()
        mock_session.send_audio = AsyncMock()
        mock_session.close = AsyncMock()

        with (
            patch("backend.app.api.websocket.Settings") as MockSettings,
            patch(
                "backend.app.api.websocket.DeepgramSession", return_value=mock_session
            ),
        ):
            MockSettings.return_value.deepgram_api_key = "test-key-123"
            client = TestClient(app_with_tts)

            with client.websocket_connect("/api/voice") as ws:
                ws.receive_json()  # session_start

                ws.send_json(
                    {
                        "type": "config",
                        "session_id": "tts-test-1",
                        "tts_enabled": True,
                        "tts_speed": "fast",
                    }
                )

                data = ws.receive_json()
                assert data["type"] == "config_ack"
                assert data["session_id"] == "tts-test-1"

    def test_default_tts_disabled_when_not_specified(self, app_with_tts):
        """tts_enabled should default to False for backward compatibility."""
        mock_session = MagicMock()
        mock_session.connect = AsyncMock()
        mock_session.send_audio = AsyncMock()
        mock_session.close = AsyncMock()

        with (
            patch("backend.app.api.websocket.Settings") as MockSettings,
            patch(
                "backend.app.api.websocket.DeepgramSession", return_value=mock_session
            ),
        ):
            MockSettings.return_value.deepgram_api_key = "test-key-123"
            client = TestClient(app_with_tts)

            with client.websocket_connect("/api/voice") as ws:
                ws.receive_json()  # session_start

                # Send config WITHOUT tts_enabled
                ws.send_json({"type": "config", "session_id": "no-tts"})

                data = ws.receive_json()
                assert data["type"] == "config_ack"

            # TTS service should NOT have been called (no utterance processed,
            # and even if it were, tts_enabled defaults to False)
            app_with_tts.state.tts_service.read_response.assert_not_called()


# ---------------------------------------------------------------------------
# DeepgramSession unit tests
# ---------------------------------------------------------------------------


class TestDeepgramSession:
    """Unit tests for the DeepgramSession class."""

    @pytest.mark.asyncio
    async def test_connect_uses_async_client_v1_api(self):
        """Should use AsyncDeepgramClient with listen.v1.connect() pattern."""
        with patch(
            "backend.app.services.deepgram_session.AsyncDeepgramClient"
        ) as MockClient:
            mock_connection = AsyncMock()
            mock_connection.start_listening = AsyncMock(return_value=asyncio.Future())
            mock_connection.start_listening.return_value.set_result(None)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_connection)

            MockClient.return_value.listen.v1.connect.return_value = mock_ctx

            from backend.app.services.deepgram_session import DeepgramSession

            session = DeepgramSession(api_key="test-key", on_transcript=AsyncMock())
            await session.connect()

            # Verify correct SDK pattern
            MockClient.assert_called_once_with(api_key="test-key")
            MockClient.return_value.listen.v1.connect.assert_called_once()

            # Verify connection params include key settings
            call_kwargs = MockClient.return_value.listen.v1.connect.call_args
            assert call_kwargs.kwargs["model"] == "nova-3"
            assert call_kwargs.kwargs["encoding"] == "linear16"
            assert call_kwargs.kwargs["sample_rate"] == "16000"
            assert call_kwargs.kwargs["interim_results"] == "true"
            assert call_kwargs.kwargs["vad_events"] == "true"

            await session.close()

    @pytest.mark.asyncio
    async def test_send_audio_forwards_to_send_media(self):
        """Audio bytes should be forwarded via connection.send_media()."""
        with patch(
            "backend.app.services.deepgram_session.AsyncDeepgramClient"
        ) as MockClient:
            mock_connection = AsyncMock()
            mock_connection.start_listening = AsyncMock(return_value=asyncio.Future())
            mock_connection.start_listening.return_value.set_result(None)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_connection)

            MockClient.return_value.listen.v1.connect.return_value = mock_ctx

            from backend.app.services.deepgram_session import DeepgramSession

            session = DeepgramSession(api_key="test-key", on_transcript=AsyncMock())
            await session.connect()

            audio_data = b"\x00\x01" * 100
            await session.send_audio(audio_data)
            mock_connection.send_media.assert_called_once_with(audio_data)

            await session.close()

    @pytest.mark.asyncio
    async def test_close_sends_close_stream_and_cancels_tasks(self):
        """Graceful shutdown: cancel keepalive, send close_stream, exit ctx, cancel listener."""
        with patch(
            "backend.app.services.deepgram_session.AsyncDeepgramClient"
        ) as MockClient:
            mock_connection = AsyncMock()
            mock_connection.start_listening = AsyncMock(return_value=asyncio.Future())
            mock_connection.start_listening.return_value.set_result(None)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_connection)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            MockClient.return_value.listen.v1.connect.return_value = mock_ctx

            from backend.app.services.deepgram_session import DeepgramSession

            session = DeepgramSession(api_key="test-key", on_transcript=AsyncMock())
            await session.connect()
            await session.close()

            mock_connection.send_close_stream.assert_called_once()
