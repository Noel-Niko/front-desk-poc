"""WebSocket endpoint for voice input via Deepgram + TTS output via Cartesia.

Adapted from the working implementation in poc-deepgram
(/Users/xnxn040/PycharmProjects/poc-deepgram/src/poc_deepgram/app.py).

Key architecture:
  - Uses DeepgramSession for STT (speech-to-text)
  - Uses CartesiaSession for TTS (text-to-speech) when enabled
  - LLM streaming: chat_streaming() yields text deltas → SentenceSplitter → CartesiaSession
  - Protocol: tts_start JSON → binary PCM16 frames → tts_end JSON
  - Barge-in: client sends tts_interrupt, server cancels TTS via asyncio.Event
  - TTS errors never block text response delivery
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.config import Settings
from backend.app.db.database import Database
from backend.app.services.cartesia_tts import strip_markdown
from backend.app.services.deepgram_session import DeepgramSession
from backend.app.services.llm import LLMService
from backend.app.services.sentence_splitter import SentenceSplitter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/api/voice")
async def voice_websocket(websocket: WebSocket) -> None:
    """Handle voice input via WebSocket.

    Protocol:
    - Client sends JSON config: {"type": "config", "session_id": "..."}
    - Client sends binary frames: raw PCM16 audio at 16kHz mono
    - Server sends JSON: {"type": "session_start"}
    - Server sends JSON: {"type": "config_ack", "session_id": "..."}
    - Server sends JSON: {"type": "transcript", "text": "...", "is_final": bool}
    - Server sends JSON: {"type": "response", "text": "...", "citations": [...]}
    - Server sends JSON: {"type": "error", "message": "..."}
    """
    await websocket.accept()

    settings = Settings()
    db: Database = websocket.app.state.db
    llm_service: LLMService = websocket.app.state.llm_service
    tts_service = getattr(websocket.app.state, "tts_service", None)

    session_id: str | None = None
    session: DeepgramSession | None = None
    tts_enabled: bool = False
    tts_speed: str = "normal"
    tts_cancel_event = asyncio.Event()

    # Gate: no Deepgram key → send error and close immediately
    if not settings.deepgram_api_key:
        await websocket.send_json(
            {
                "type": "error",
                "message": "Deepgram API key not configured. Use text input.",
            }
        )
        await websocket.close()
        return

    # Accumulate final transcript parts until speech_final signals utterance end
    final_parts: list[str] = []
    # Track background LLM tasks so we can await them on cleanup
    pending_tasks: list[asyncio.Task] = []

    async def process_utterance(text: str) -> None:
        """Process a completed utterance with streaming LLM + TTS pipeline.

        Pipeline:
          1. chat_streaming() yields text deltas and tool events
          2. SentenceSplitter accumulates deltas into sentences
          3. CartesiaSession synthesizes each sentence (if TTS enabled)
          4. Audio chunks forwarded as binary WebSocket frames

        Runs as a background task so it doesn't block the Deepgram listener.
        """
        try:
            # Save user message
            await db.insert(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, 'user', ?, ?)",
                (session_id, text, datetime.now().isoformat()),
            )

            # Clear cancel event for this utterance
            tts_cancel_event.clear()

            # Audio callback: forwards Cartesia audio to browser as binary frames
            audio_chunks_sent = 0

            async def on_audio_chunk(audio_bytes: bytes) -> None:
                nonlocal audio_chunks_sent
                if not tts_cancel_event.is_set():
                    await websocket.send_bytes(audio_bytes)
                    audio_chunks_sent += 1

            splitter = SentenceSplitter()
            tts_active = tts_enabled and tts_service is not None
            logger.info(
                "TTS pipeline: tts_enabled=%s, tts_service=%s, tts_active=%s",
                tts_enabled,
                tts_service is not None,
                tts_active,
            )

            if tts_active:
                await tts_service.start_utterance(on_audio_chunk)
                await websocket.send_json({"type": "tts_start"})

            # Stream LLM response
            done_event = None
            async for event in llm_service.chat_streaming(session_id, text):
                if tts_cancel_event.is_set() and tts_active:
                    await tts_service.cancel_utterance()
                    tts_active = False

                if event["type"] == "text_delta":
                    # Send progressive text to browser
                    await websocket.send_json(
                        {
                            "type": "response_delta",
                            "text": event["text"],
                        }
                    )

                    # Feed to sentence splitter for TTS
                    if tts_active:
                        clean_token = strip_markdown(event["text"])
                        if clean_token:
                            for sentence in splitter.push(clean_token):
                                if tts_cancel_event.is_set():
                                    await tts_service.cancel_utterance()
                                    tts_active = False
                                    break
                                await tts_service.push_sentence(sentence)

                elif event["type"] == "done":
                    done_event = event

            # Flush remaining text to TTS
            if tts_active:
                remainder = splitter.flush()
                if remainder and not tts_cancel_event.is_set():
                    logger.info("TTS flush remainder: %s", remainder[:80])
                    await tts_service.push_sentence(remainder)
                if not tts_cancel_event.is_set():
                    await tts_service.finish_utterance()
                else:
                    await tts_service.cancel_utterance()
                logger.info(
                    "TTS pipeline done: %d audio chunks sent to client",
                    audio_chunks_sent,
                )
                await websocket.send_json({"type": "tts_end"})

            if done_event:
                # Save assistant message
                citations_json = (
                    json.dumps(done_event["citations"])
                    if done_event["citations"]
                    else None
                )
                await db.insert(
                    """INSERT INTO messages
                       (session_id, role, content, citations, tool_used, timestamp)
                       VALUES (?, 'assistant', ?, ?, ?, ?)""",
                    (
                        session_id,
                        done_event["full_text"],
                        citations_json,
                        done_event["tool_used"],
                        datetime.now().isoformat(),
                    ),
                )

                # Send final response with metadata
                await websocket.send_json(
                    {
                        "type": "response",
                        "text": done_event["full_text"],
                        "citations": done_event["citations"],
                        "tool_used": done_event["tool_used"],
                        "transferred": done_event["transferred"],
                        "transfer_reason": done_event["transfer_reason"],
                    }
                )

        except Exception:
            logger.exception("Error processing utterance: %s", text[:100])
            try:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Failed to process your message. Please try again.",
                    }
                )
            except Exception:
                pass

    async def on_transcript(event: dict) -> None:
        """Forward Deepgram events to the browser client.

        IMPORTANT: This callback is invoked from the Deepgram listener task.
        It must return quickly — blocking here prevents all subsequent
        transcript events from being processed. LLM calls are dispatched
        to a background task via asyncio.create_task().
        """
        nonlocal final_parts

        try:
            transcript = event["transcript"]
            is_final = event["type"] == "final"
            speech_final = event.get("speech_final", False)

            if is_final:
                final_parts.append(transcript)

            if speech_final and final_parts:
                # End of utterance — join all final parts
                full_text = " ".join(final_parts)
                final_parts.clear()

                # Send final transcript to client immediately
                await websocket.send_json(
                    {
                        "type": "transcript",
                        "text": full_text,
                        "is_final": True,
                    }
                )

                # Process LLM in background — don't block Deepgram handler
                if session_id and full_text.strip():
                    task = asyncio.create_task(process_utterance(full_text))
                    pending_tasks.append(task)
                    task.add_done_callback(
                        lambda t: (
                            pending_tasks.remove(t) if t in pending_tasks else None
                        )
                    )
            else:
                # Interim or non-final confirmed partial — show as interim
                await websocket.send_json(
                    {
                        "type": "transcript",
                        "text": transcript,
                        "is_final": False,
                    }
                )
        except Exception:
            logger.exception("Error in on_transcript callback")

    try:
        # Create and connect Deepgram session BEFORE entering receive loop
        session = DeepgramSession(
            api_key=settings.deepgram_api_key,
            on_transcript=on_transcript,
        )
        await session.connect()
        logger.info("Deepgram session connected")

        # Notify client that server is ready
        await websocket.send_json({"type": "session_start"})

        # Main loop: receive from browser, dispatch by type
        while True:
            data = await websocket.receive()

            if "text" in data:
                # JSON message (config, tts_interrupt, etc.)
                msg = json.loads(data["text"])
                if msg.get("type") == "config":
                    session_id = msg.get("session_id", str(uuid.uuid4()))
                    tts_enabled = msg.get("tts_enabled", False)
                    tts_speed = msg.get("tts_speed", "normal")  # noqa: F841
                    # Ensure session exists in DB
                    existing = await db.fetch_one(
                        "SELECT id FROM sessions WHERE id = ?", (session_id,)
                    )
                    if existing is None:
                        await db.insert(
                            "INSERT INTO sessions (id, started_at, input_mode) VALUES (?, ?, 'voice')",
                            (session_id, datetime.now().isoformat()),
                        )
                    await websocket.send_json(
                        {
                            "type": "config_ack",
                            "session_id": session_id,
                        }
                    )
                elif msg.get("type") == "tts_interrupt":
                    tts_cancel_event.set()
                    logger.info("TTS interrupted by user (session: %s)", session_id)

            elif "bytes" in data:
                # Binary audio data — forward to Deepgram
                await session.send_audio(data["bytes"])

    except WebSocketDisconnect:
        logger.info("Voice WebSocket disconnected (session: %s)", session_id)
    except Exception:
        logger.exception("Voice WebSocket error")
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Internal server error",
                }
            )
        except Exception:
            pass
    finally:
        if session:
            await session.close()
            logger.info("Deepgram session closed (session: %s)", session_id)
