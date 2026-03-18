"""Deepgram WebSocket session management.

Adapted from the working implementation in poc-deepgram
(/Users/xnxn040/PycharmProjects/poc-deepgram/src/poc_deepgram/deepgram_client.py).

Uses the Deepgram SDK v6 async API:
  - AsyncDeepgramClient (not sync DeepgramClient)
  - listen.v1.connect() with keyword args (not LiveOptions object)
  - Context manager + start_listening() background task
  - 10s keepalive loop to prevent timeout during silence
  - Graceful shutdown: cancel keepalive → send_close_stream → exit ctx → cancel listener

One DeepgramSession instance per browser WebSocket connection.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.listen.v1.types import ListenV1Results

logger = logging.getLogger(__name__)


class DeepgramSession:
    """Manages a single async Deepgram WebSocket session."""

    def __init__(
        self,
        api_key: str,
        on_transcript: Callable[[dict], Awaitable[None]],
    ) -> None:
        self._client = AsyncDeepgramClient(api_key=api_key)
        self._on_transcript = on_transcript
        self._connection: Any = None
        self._ctx_manager: Any = None
        self._listener_task: asyncio.Task | None = None
        self._keepalive_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Open Deepgram WebSocket and start listener + keepalive background tasks.

        Uses the listen.v1.connect() context manager API (Deepgram SDK v6).
        Event handlers are registered BEFORE start_listening() is called —
        this is required to avoid missing the first transcript events.
        """
        self._ctx_manager = self._client.listen.v1.connect(
            model="nova-3",
            encoding="linear16",
            sample_rate="16000",
            channels="1",
            interim_results="true",
            utterance_end_ms="1500",
            vad_events="true",
            smart_format="true",
            punctuate="true",
            language="en",
        )
        self._connection = await self._ctx_manager.__aenter__()

        # Register event handlers BEFORE starting listener (order matters)
        self._connection.on(EventType.MESSAGE, self._handle_message)
        self._connection.on(EventType.ERROR, self._handle_error)

        # start_listening() blocks until connection closes — run as background task
        self._listener_task = asyncio.create_task(self._connection.start_listening())
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def _handle_message(self, message: Any) -> None:
        """Dispatch Deepgram transcript events to the on_transcript callback.

        Wrapped in try/except to prevent callback errors from killing
        the listener task (which would stop all future transcript processing).
        """
        try:
            if isinstance(message, ListenV1Results):
                alt = message.channel.alternatives[0] if message.channel.alternatives else None
                if alt and alt.transcript:
                    event = {
                        "type": "final" if message.is_final else "interim",
                        "speech_final": message.speech_final,
                        "transcript": alt.transcript,
                        "confidence": alt.confidence,
                    }
                    await self._on_transcript(event)
        except Exception:
            logger.exception("Error in Deepgram message handler")

    async def _handle_error(self, error: Any) -> None:
        """Log Deepgram errors."""
        logger.error("Deepgram error: %s", error)

    async def _keepalive_loop(self) -> None:
        """Send keep-alive every 10s to prevent Deepgram timeout during silence.

        Without this, Deepgram disconnects after ~30s of no audio.
        See: poc-deepgram/src/poc_deepgram/deepgram_client.py
        """
        try:
            while True:
                await asyncio.sleep(10)
                if self._connection:
                    await self._connection.send_keep_alive()
        except asyncio.CancelledError:
            pass

    async def send_audio(self, audio_bytes: bytes) -> None:
        """Forward raw PCM16 audio bytes to Deepgram."""
        if self._connection:
            await self._connection.send_media(audio_bytes)

    async def close(self) -> None:
        """Gracefully shut down the Deepgram session.

        Shutdown order matters:
        1. Cancel keepalive (stop sending pings)
        2. Send close_stream (let Deepgram flush final results)
        3. Exit context manager (release resources)
        4. Cancel listener task (stop receiving)
        """
        if self._keepalive_task:
            self._keepalive_task.cancel()
        if self._connection:
            try:
                await self._connection.send_close_stream()
            except Exception:
                pass
        if self._ctx_manager:
            try:
                await self._ctx_manager.__aexit__(None, None, None)
            except Exception:
                pass
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
