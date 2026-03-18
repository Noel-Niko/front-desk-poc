"""WebSocket endpoint for voice input via Deepgram.

Adapted from the working implementation in poc-deepgram
(/Users/xnxn040/PycharmProjects/poc-deepgram/src/poc_deepgram/app.py).

Key differences from the original broken implementation:
  - Uses DeepgramSession (AsyncDeepgramClient + listen.v1.connect API)
    instead of the old DeepgramClient + LiveOptions + .start() API
  - Creates Deepgram session BEFORE entering the receive loop
  - Has keepalive loop to prevent Deepgram timeout
  - Proper graceful shutdown via session.close() in finally block
  - Accumulates final transcript parts; processes with LLM on speech_final
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.config import Settings
from backend.app.db.database import Database
from backend.app.services.deepgram_session import DeepgramSession
from backend.app.services.llm import LLMService

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

    session_id: str | None = None
    session: DeepgramSession | None = None

    # Gate: no Deepgram key → send error and close immediately
    if not settings.deepgram_api_key:
        await websocket.send_json({
            "type": "error",
            "message": "Deepgram API key not configured. Use text input.",
        })
        await websocket.close()
        return

    # Accumulate final transcript parts until speech_final signals utterance end
    final_parts: list[str] = []
    # Track background LLM tasks so we can await them on cleanup
    pending_tasks: list[asyncio.Task] = []

    async def process_utterance(text: str) -> None:
        """Process a completed utterance with the LLM.

        Runs as a background task so it doesn't block the Deepgram listener.
        Has its own error handling to prevent silent failures.
        """
        try:
            # Save user message
            await db.insert(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, 'user', ?, ?)",
                (session_id, text, datetime.now().isoformat()),
            )

            # Get LLM response
            result = await llm_service.chat(session_id, text)

            # Save assistant message
            citations_json = json.dumps(result["citations"]) if result["citations"] else None
            await db.insert(
                """INSERT INTO messages
                   (session_id, role, content, citations, tool_used, timestamp)
                   VALUES (?, 'assistant', ?, ?, ?, ?)""",
                (session_id, result["message"], citations_json,
                 result["tool_used"], datetime.now().isoformat()),
            )

            # Send response to client
            await websocket.send_json({
                "type": "response",
                "text": result["message"],
                "citations": result["citations"],
                "tool_used": result["tool_used"],
                "transferred": result["transferred"],
                "transfer_reason": result["transfer_reason"],
            })
        except Exception:
            logger.exception("Error processing utterance: %s", text[:100])
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to process your message. Please try again.",
                })
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
                await websocket.send_json({
                    "type": "transcript",
                    "text": full_text,
                    "is_final": True,
                })

                # Process LLM in background — don't block Deepgram handler
                if session_id and full_text.strip():
                    task = asyncio.create_task(process_utterance(full_text))
                    pending_tasks.append(task)
                    task.add_done_callback(lambda t: pending_tasks.remove(t) if t in pending_tasks else None)
            else:
                # Interim or non-final confirmed partial — show as interim
                await websocket.send_json({
                    "type": "transcript",
                    "text": transcript,
                    "is_final": False,
                })
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
                # JSON message (config, etc.)
                msg = json.loads(data["text"])
                if msg.get("type") == "config":
                    session_id = msg.get("session_id", str(uuid.uuid4()))
                    # Ensure session exists in DB
                    existing = await db.fetch_one(
                        "SELECT id FROM sessions WHERE id = ?", (session_id,)
                    )
                    if existing is None:
                        await db.insert(
                            "INSERT INTO sessions (id, started_at, input_mode) VALUES (?, ?, 'voice')",
                            (session_id, datetime.now().isoformat()),
                        )
                    await websocket.send_json({
                        "type": "config_ack",
                        "session_id": session_id,
                    })

            elif "bytes" in data:
                # Binary audio data — forward to Deepgram
                await session.send_audio(data["bytes"])

    except WebSocketDisconnect:
        logger.info("Voice WebSocket disconnected (session: %s)", session_id)
    except Exception:
        logger.exception("Voice WebSocket error")
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Internal server error",
            })
        except Exception:
            pass
    finally:
        if session:
            await session.close()
            logger.info("Deepgram session closed (session: %s)", session_id)
