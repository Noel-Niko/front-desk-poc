"""Cartesia TTS service for voice output.

Handles text-to-speech synthesis with sentence-level streaming.
Uses the Cartesia WebSocket API for low-latency audio streaming.

Architecture:
  - strip_markdown() cleans LLM output for natural speech
  - split_into_sentences() breaks text at sentence boundaries
  - CartesiaTTSService.read_response() orchestrates the pipeline:
    tts_start JSON → binary PCM16 frames per sentence → tts_end JSON

One CartesiaTTSService instance per application (created in lifespan).
The _synthesize_sentence() method is the integration point with the
Cartesia SDK — see docs/cartesia_ws_research.md for SDK specifics.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Abbreviations that should NOT trigger sentence splits
_ABBREVIATIONS = {"Dr", "Mr", "Mrs", "Ms", "Jr", "Sr", "Prof", "St", "Ave", "vs", "etc", "i.e", "e.g"}


def strip_markdown(text: str | None) -> str:
    """Strip markdown formatting from text for TTS.

    Removes headers, bold, italic, links, code blocks, inline code,
    list markers, and horizontal rules.
    """
    if not text:
        return ""

    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)

    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove headers (### Header -> Header)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove bold (**text** -> text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)

    # Remove italic (*text* -> text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)

    # Remove links ([text](url) -> text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove list markers (-, *, 1., 2., etc.)
    text = re.sub(r"^[\s]*[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}$", "", text, flags=re.MULTILINE)

    # Clean up multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Clean up extra whitespace
    text = re.sub(r" {2,}", " ", text)

    return text.strip()


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences for progressive TTS synthesis.

    Splits on sentence-ending punctuation (.!?) followed by whitespace
    or newlines, while preserving common abbreviations (Dr., Mrs., etc.)
    and ellipsis (...).
    """
    if not text:
        return []

    # Split on sentence boundaries: .!? followed by space/newline or end of string
    # Use negative lookbehind for common abbreviations
    abbr_pattern = "|".join(re.escape(a) for a in _ABBREVIATIONS)
    sentence_pattern = rf"(?<!{abbr_pattern})(?<=[.!?])\s+"
    # Simpler approach: split on .!? followed by whitespace, then rejoin abbreviations
    # The regex approach for abbreviations is fragile; use a two-pass method instead.

    sentences: list[str] = []
    current = ""

    # First, protect ellipsis from being split on
    text = re.sub(r"\.{3}", "\x00ELLIPSIS\x00", text)

    # Tokenize by splitting on whitespace-after-punctuation boundaries
    # Handle newlines as boundaries too
    parts = re.split(r"(?<=[\.\!\?])\s+|\n+", text)

    # Restore ellipsis
    parts = [p.replace("\x00ELLIPSIS\x00", "...") for p in parts]

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check if the previous fragment ended with an abbreviation
        if current and _ends_with_abbreviation(current):
            current += " " + part
        else:
            if current:
                sentences.append(current)
            current = part

    if current:
        sentences.append(current)

    return [s.strip() for s in sentences if s.strip()]


def _ends_with_abbreviation(text: str) -> bool:
    """Check if text ends with a known abbreviation."""
    for abbr in _ABBREVIATIONS:
        if text.endswith(abbr + "."):
            return True
    return False


class CartesiaTTSService:
    """Manages TTS synthesis via Cartesia.

    read_response() is the main entry point:
    1. Strip markdown from LLM output
    2. Split into sentences
    3. For each sentence: synthesize → send binary frame
    4. Wrap with tts_start/tts_end JSON messages

    _synthesize_sentence() is the Cartesia SDK integration point.
    # TODO: integrate Cartesia WebSocket SDK (see docs/cartesia_ws_research.md)
    """

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model_id: str = "sonic-3",
    ) -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._client = None  # TODO: Cartesia WebSocket client (see docs/cartesia_ws_research.md)

    async def read_response(
        self,
        text: str,
        websocket: WebSocket,
        speed: Literal["slow", "normal", "fast"] = "normal",
    ) -> None:
        """Synthesize text and stream audio to the browser WebSocket.

        Protocol:
          1. Send {"type": "tts_start"} JSON
          2. For each sentence: synthesize → send raw PCM16 binary frame
          3. Send {"type": "tts_end"} JSON

        Errors are caught and logged — TTS failure must never block text delivery.
        """
        if not self._api_key:
            return

        if not text or not text.strip():
            return

        try:
            clean_text = strip_markdown(text)
            if not clean_text or not clean_text.strip():
                return

            sentences = split_into_sentences(clean_text)
            if not sentences:
                return

            await websocket.send_json({"type": "tts_start"})

            for sentence in sentences:
                if not sentence.strip():
                    continue
                audio_bytes = await self._synthesize_sentence(sentence, speed=speed)
                if audio_bytes:
                    await websocket.send_bytes(audio_bytes)

            await websocket.send_json({"type": "tts_end"})

        except Exception:
            logger.exception("TTS synthesis failed")

    async def _synthesize_sentence(
        self,
        text: str,
        speed: Literal["slow", "normal", "fast"] = "normal",
    ) -> bytes | None:
        """Synthesize a single sentence to PCM16 audio bytes.

        # TODO: integrate Cartesia WebSocket SDK (see docs/cartesia_ws_research.md)
        # This method will use the Cartesia WebSocket connection with
        # continuation support for natural prosody across sentences.
        """
        logger.warning("Cartesia SDK integration pending — see docs/cartesia_ws_research.md")
        return None

    async def close(self) -> None:
        """Close the Cartesia client connection."""
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
