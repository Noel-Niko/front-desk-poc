"""Streaming sentence splitter for the TTS pipeline.

Accumulates text tokens from the LLM stream and yields complete sentences
when a sentence boundary is detected. Designed for token-by-token input
from Claude's streaming API.

Key features:
  - Sentence boundary detection on .!? followed by whitespace
  - Abbreviation preservation (Dr., Mrs., Mr., Ms., Prof., etc.)
  - Decimal number preservation (3.14, $125.00)
  - Minimum chunk length batching to avoid tiny TTS requests
  - Newline boundary handling
  - flush() for remaining text at end of stream

The batch counterpart `split_into_sentences()` in cartesia_tts.py handles
complete text. This class handles streaming token-by-token input.
"""

from __future__ import annotations

import re

# Common abbreviations that end with a period but aren't sentence endings.
# Shared concept with _ABBREVIATIONS in cartesia_tts.py but expanded for
# streaming context where we see the word just before the period.
ABBREVIATIONS = frozenset({
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "ave", "blvd",
    "dept", "est", "govt", "inc", "ltd", "mgr", "no", "rm", "vs",
    "approx", "appt", "ext", "misc",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug",
    "sep", "oct", "nov", "dec",
    "a.m", "p.m",
})

# Minimum character count before yielding a sentence to TTS
MIN_CHUNK_LENGTH = 30


class SentenceSplitter:
    """Accumulates streaming text tokens and yields complete sentences.

    Usage::

        splitter = SentenceSplitter()
        for token in llm_stream:
            for sentence in splitter.push(token):
                await tts.push_sentence(sentence)
        remaining = splitter.flush()
        if remaining:
            await tts.push_sentence(remaining)
    """

    def __init__(self, min_length: int = MIN_CHUNK_LENGTH) -> None:
        self._buffer = ""
        self._min_length = min_length

    def push(self, token: str) -> list[str]:
        """Add a token to the buffer and return any complete sentences."""
        self._buffer += token
        return self._extract_sentences()

    def flush(self) -> str | None:
        """Return any remaining text in the buffer."""
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining if remaining else None

    def _extract_sentences(self) -> list[str]:
        """Extract complete sentences from the buffer."""
        sentences: list[str] = []

        while True:
            # Find potential sentence boundary: .!? followed by whitespace
            match = re.search(r"([.!?])\s+", self._buffer)
            if not match:
                # Check for newline boundary
                newline_pos = self._buffer.find("\n")
                if newline_pos > 0:
                    candidate = self._buffer[:newline_pos].strip()
                    if len(candidate) >= self._min_length:
                        sentences.append(candidate)
                        self._buffer = self._buffer[newline_pos + 1:]
                        continue
                break

            pos = match.end()
            # candidate includes the punctuation but not the trailing space
            candidate = self._buffer[:match.start() + 1].strip()

            # Check if the period is part of an abbreviation
            if match.group(1) == ".":
                if self._is_abbreviation(candidate):
                    # Not a sentence end — try to find next boundary
                    next_match = re.search(r"([.!?])\s+", self._buffer[pos:])
                    if not next_match:
                        break
                    # Extend candidate to next boundary
                    pos = pos + next_match.end()
                    candidate = self._buffer[:pos - len(next_match.group()) + 1].strip()
                    # Re-check if this new candidate also ends with abbreviation
                    if self._is_abbreviation(candidate):
                        break

                # Check if the specific boundary period is part of a decimal
                # (e.g., "3.14 " or "$125.00 ") — look at chars around the match
                boundary_pos = match.start()
                if self._is_decimal_at(boundary_pos):
                    # Try next boundary
                    next_match = re.search(r"([.!?])\s+", self._buffer[pos:])
                    if not next_match:
                        break
                    pos = pos + next_match.end()
                    candidate = self._buffer[:pos - len(next_match.group()) + 1].strip()

            # Only yield if we have enough text
            if len(candidate) >= self._min_length:
                sentences.append(candidate)
                self._buffer = self._buffer[pos:]
            else:
                # Too short — try to accumulate more by finding next boundary
                next_match = re.search(r"([.!?])\s+", self._buffer[pos:])
                if not next_match:
                    break
                # Extend to include next sentence too
                combined_end = pos + next_match.end()
                combined = self._buffer[:combined_end - len(next_match.group()) + 1].strip()
                if len(combined) >= self._min_length:
                    sentences.append(combined)
                    self._buffer = self._buffer[combined_end:]
                else:
                    break

        return sentences

    def _is_abbreviation(self, text: str) -> bool:
        """Check if text ends with a known abbreviation."""
        # Handle "a.m." / "p.m." pattern
        if text.endswith("."):
            # Check last two-word abbreviation (e.g., "a.m.")
            if len(text) >= 4:
                last_four = text[-4:].lower()
                if last_four in {"a.m.", "p.m."}:
                    return True

            # Get the last word before the period
            stripped = text.rstrip(".")
            words = stripped.split()
            if words:
                last_word = words[-1].lower().rstrip(".")
                if last_word in ABBREVIATIONS:
                    return True
        return False

    def _is_decimal_at(self, period_pos: int) -> bool:
        """Check if the period at period_pos in the buffer is part of a decimal."""
        # A decimal period has a digit before AND after it: "3.14", "$125.00"
        if period_pos > 0 and period_pos < len(self._buffer) - 1:
            char_before = self._buffer[period_pos - 1]
            char_after = self._buffer[period_pos + 1]
            return char_before.isdigit() and char_after.isdigit()
        return False
