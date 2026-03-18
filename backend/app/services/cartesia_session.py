"""Cartesia WebSocket TTS session manager.

Manages a persistent WebSocket connection to Cartesia's TTS service.
Models the same lifecycle pattern as DeepgramSession:
  - One instance per application (singleton on app.state)
  - connect() opens the WebSocket at startup
  - start_utterance() / push_sentence() / finish_utterance() per response
  - cancel_utterance() for barge-in
  - close() at shutdown

Architecture:
  - One persistent WebSocket connection, reusable across utterances
  - Each utterance creates a separate Cartesia "context" with consistent prosody
  - Audio chunks are forwarded via an async callback (on_audio)
  - A background receive loop streams audio as Cartesia synthesizes

See docs/cartesia_ws_research.md for SDK API details.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from cartesia import AsyncCartesia

logger = logging.getLogger(__name__)

# Cartesia output format: raw PCM16 at 24kHz mono
OUTPUT_FORMAT = {
    "container": "raw",
    "encoding": "pcm_s16le",
    "sample_rate": 24000,
}

# Default TTS model
DEFAULT_MODEL_ID = "sonic-3"


class CartesiaSession:
    """Manages a Cartesia WebSocket TTS connection.

    Usage::

        session = CartesiaSession(api_key="...", voice_id="...")
        await session.connect()

        # Per utterance:
        await session.start_utterance(on_audio_callback)
        await session.push_sentence("Hello world.")
        await session.push_sentence("How can I help?")
        await session.finish_utterance()

        # Barge-in:
        await session.cancel_utterance()

        # Shutdown:
        await session.close()
    """

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model_id: str = DEFAULT_MODEL_ID,
    ) -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._client: AsyncCartesia | None = None
        self._ws_ctx_manager: Any = None
        self._connection: Any = None
        self._current_ctx: Any = None
        self._receive_task: asyncio.Task | None = None
        self._on_audio: Callable[[bytes], Awaitable[None]] | None = None

    async def connect(self) -> None:
        """Open a persistent Cartesia WebSocket connection.

        No-op if API key is empty (TTS disabled).
        """
        if not self._api_key:
            return

        self._client = AsyncCartesia(api_key=self._api_key)
        self._ws_ctx_manager = self._client.tts.websocket_connect()
        self._connection = await self._ws_ctx_manager.__aenter__()
        logger.info("Cartesia WebSocket connected")

    async def _ensure_connected(self) -> None:
        """Reconnect if the persistent WebSocket has gone stale."""
        if self._connection is not None:
            return
        if not self._api_key:
            return
        logger.info("Cartesia WebSocket reconnecting...")
        await self.close()
        self._client = AsyncCartesia(api_key=self._api_key)
        self._ws_ctx_manager = self._client.tts.websocket_connect()
        self._connection = await self._ws_ctx_manager.__aenter__()
        logger.info("Cartesia WebSocket reconnected")

    async def start_utterance(
        self,
        on_audio: Callable[[bytes], Awaitable[None]],
    ) -> None:
        """Create a new Cartesia context for synthesizing a response.

        Args:
            on_audio: Async callback invoked with raw PCM16 bytes for each
                      audio chunk. Typically sends to the browser WebSocket.
        """
        await self._ensure_connected()
        if not self._connection:
            logger.warning("CartesiaSession: no connection, skipping TTS")
            return

        self._on_audio = on_audio
        try:
            self._current_ctx = self._connection.context(
                model_id=self._model_id,
                voice={"mode": "id", "id": self._voice_id},
                output_format=OUTPUT_FORMAT,
            )
        except Exception:
            logger.exception("Failed to create Cartesia context, reconnecting")
            self._connection = None
            await self._ensure_connected()
            if not self._connection:
                return
            self._current_ctx = self._connection.context(
                model_id=self._model_id,
                voice={"mode": "id", "id": self._voice_id},
                output_format=OUTPUT_FORMAT,
            )
        logger.info("Cartesia utterance started")
        # Start receiving audio chunks in background
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def push_sentence(self, text: str) -> None:
        """Push a sentence to Cartesia for synthesis.

        The Cartesia SDK uses continuation: text pushed within the same
        context maintains natural prosody across sentences.
        """
        if self._current_ctx:
            logger.debug("Cartesia push: %s", text[:80])
            await self._current_ctx.push(text)
        else:
            logger.warning("push_sentence called with no active context")

    async def finish_utterance(self) -> None:
        """Signal no more text for this utterance and wait for audio to drain."""
        if self._current_ctx:
            await self._current_ctx.no_more_inputs()
        # Wait for all audio to be received and forwarded
        if self._receive_task:
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        self._current_ctx = None

    async def cancel_utterance(self) -> None:
        """Cancel current synthesis (barge-in).

        Cancels the background receive loop and clears the context.
        """
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        self._current_ctx = None

    async def close(self) -> None:
        """Gracefully close the Cartesia connection.

        Shutdown order:
        1. Cancel any active utterance
        2. Exit WebSocket context manager
        3. Close the client
        """
        await self.cancel_utterance()
        if self._ws_ctx_manager:
            try:
                await self._ws_ctx_manager.__aexit__(None, None, None)
            except Exception:
                pass
            self._ws_ctx_manager = None
        self._connection = None
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
        logger.info("Cartesia WebSocket closed")

    async def _receive_loop(self) -> None:
        """Receive audio chunks from Cartesia and forward via callback."""
        chunk_count = 0
        try:
            if self._current_ctx and self._on_audio:
                async for response in self._current_ctx.receive():
                    if response.type == "chunk" and response.audio:
                        chunk_count += 1
                        await self._on_audio(response.audio)
                    elif response.type == "error":
                        logger.error("Cartesia error response: %s", response)
                    # done/flush_done/timestamps are informational, skip
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error receiving Cartesia audio")
        finally:
            logger.info("Cartesia receive loop done: %d chunks forwarded", chunk_count)
