"""WebSocket endpoint for voice input via Deepgram."""

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.config import Settings
from backend.app.db.database import Database
from backend.app.services.llm import LLMService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/api/voice")
async def voice_websocket(websocket: WebSocket) -> None:
    """Handle voice input via WebSocket.

    Protocol:
    - Client sends JSON config: {"type": "config", "session_id": "..."}
    - Client sends binary frames: raw PCM16 audio chunks
    - Server sends JSON: {"type": "transcript", "text": "...", "is_final": bool}
    - Server sends JSON: {"type": "response", "text": "...", "citations": [...]}
    - Server sends JSON: {"type": "error", "message": "..."}

    If no Deepgram API key is configured, the client should use browser
    SpeechRecognition and send final text via POST /api/chat instead.
    """
    await websocket.accept()

    settings = Settings()
    db: Database = websocket.app.state.db
    llm_service: LLMService = websocket.app.state.llm_service

    session_id: str | None = None

    if not settings.deepgram_api_key:
        await websocket.send_json({
            "type": "error",
            "message": "Deepgram API key not configured. Use text input or browser SpeechRecognition.",
        })
        await websocket.close()
        return

    try:
        from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

        deepgram = DeepgramClient(settings.deepgram_api_key)
        dg_connection = deepgram.listen.asyncwebsocket.v("1")

        # Track transcript accumulation
        final_transcript_parts: list[str] = []

        async def on_transcript(_, result, **kwargs) -> None:
            """Handle Deepgram transcript events."""
            transcript = result.channel.alternatives[0].transcript
            is_final = result.is_final

            if not transcript:
                return

            if is_final:
                final_transcript_parts.append(transcript)
                confidence = result.channel.alternatives[0].confidence
                await websocket.send_json({
                    "type": "transcript",
                    "text": transcript,
                    "is_final": True,
                    "confidence": confidence,
                })
            else:
                await websocket.send_json({
                    "type": "transcript",
                    "text": transcript,
                    "is_final": False,
                })

        async def on_utterance_end(_, result, **kwargs) -> None:
            """When an utterance ends, process the accumulated transcript."""
            if not final_transcript_parts:
                return

            full_text = " ".join(final_transcript_parts)
            final_transcript_parts.clear()

            if not full_text.strip():
                return

            if session_id is None:
                return

            logger.info("Processing utterance: %s", full_text[:100])

            # Save user message
            await db.insert(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, 'user', ?, ?)",
                (session_id, full_text, datetime.now().isoformat()),
            )

            # Get LLM response
            result = await llm_service.chat(session_id, full_text)

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

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
        dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)

        options = LiveOptions(
            model="nova-3",
            language="en-US",
            smart_format=True,
            interim_results=True,
            utterance_end_ms="1500",
            vad_events=True,
        )

        if not await dg_connection.start(options):
            await websocket.send_json({
                "type": "error",
                "message": "Failed to connect to Deepgram",
            })
            await websocket.close()
            return

        # Main loop: receive audio from client, forward to Deepgram
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
                await dg_connection.send(data["bytes"])

        await dg_connection.finish()

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
