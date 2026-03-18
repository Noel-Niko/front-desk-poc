# Cartesia WebSocket TTS — Research & Implementation Plan

## Status: REVISED — Post-Review Corrections Applied

Research conducted across: Cartesia Python SDK README (GitHub), Anthropic SDK v0.85.0 (local source), Web Audio API patterns, and sentence splitting strategies.

### Review Corrections Applied
1. Added `await` to all async Cartesia SDK calls (`ctx.push()`, `ctx.no_more_inputs()`)
2. Fixed Section 6 diagram to match Section 2's single-loop streaming pattern
3. Added `transferred`/`transfer_reason` tracking to `chat_streaming()`
4. Changed `chat_streaming()` return type to `AsyncIterator[dict]` with structured events (not just `str`)
5. Reconciled with existing `cartesia_tts.py` — refactor it, don't create a new file
6. Added `tts_interrupt` backend handler with concurrency coordination
7. Acknowledged existing TTS wiring in `websocket.py` lines 107-114
8. Model ID: `sonic-3` (Cartesia's latest per SDK README, replaces `sonic-2024-12-12`)

---

## 1. Cartesia Python SDK — Exact API Surface

### Installation

```bash
pip install 'cartesia[websockets]'
```

The `[websockets]` extra is required for WebSocket support.

### Key Classes

| Class | Module | Purpose |
|---|---|---|
| `Cartesia` | `cartesia` | Sync client |
| `AsyncCartesia` | `cartesia` | Async client (our choice) |

### WebSocket API — Exact Method Chain

```python
from cartesia import AsyncCartesia

client = AsyncCartesia(api_key="...")

# 1. Open WebSocket connection (async context manager)
async with client.tts.websocket_connect() as connection:

    # 2. Create a context (one per utterance/response)
    ctx = connection.context(
        model_id="sonic-3",
        voice={"mode": "id", "id": "2f251ac3-89a9-4a77-a452-704b474ccd01"},
        output_format={
            "container": "raw",
            "encoding": "pcm_s16le",
            "sample_rate": 24000,
        },
    )

    # 3. Push text incrementally (continuations) — MUST await
    await ctx.push("Welcome to Sunshine Learning Center. ")
    await ctx.push("How can I help you today?")

    # 4. Signal no more text — MUST await
    await ctx.no_more_inputs()

    # 5. Receive audio chunks as they're synthesized
    async for response in ctx.receive():
        if response.type == "chunk" and response.audio:
            # response.audio is bytes (raw PCM16)
            await send_audio_to_browser(response.audio)
```

### Critical API Details

- **`websocket_connect()`** — Returns a context manager. One persistent WebSocket connection, reusable for multiple contexts.
- **`connection.context(...)`** — Creates a synthesis context. Each context is one "utterance" with consistent prosody. You can have multiple concurrent contexts on one connection.
- **`ctx.push(text)`** — Send text incrementally. Cartesia starts synthesizing immediately on each push. For continuations, the prosody flows naturally across pushes within the same context.
- **`ctx.no_more_inputs()`** — Signals that no more text will be pushed. Cartesia flushes remaining audio.
- **`ctx.receive()`** — Async iterator yielding response objects. Each has `.type` ("chunk" or "done") and `.audio` (bytes or None).

### Output Format Options

| Encoding | Description | Browser Playback |
|---|---|---|
| `pcm_s16le` | Signed 16-bit little-endian PCM | Convert Int16→Float32, feed to AudioBufferSourceNode |
| `pcm_f32le` | 32-bit float little-endian PCM | Direct to AudioBufferSourceNode (no conversion) |

**Recommendation: `pcm_s16le` at 24000 Hz** — half the bandwidth of f32le, trivial conversion client-side, and 24kHz is standard for voice (human speech doesn't benefit from 44.1kHz).

### Async Version (What We'll Use)

```python
from cartesia import AsyncCartesia

client = AsyncCartesia(api_key="...")
async with client.tts.websocket_connect() as connection:
    # Same API, just use async for/await
    ctx = connection.context(...)
    await ctx.push("...")
    await ctx.no_more_inputs()
    async for response in ctx.receive():
        ...
```

### Error Handling

```python
import cartesia

try:
    ...
except cartesia.APIConnectionError:
    # Network/connection issue
except cartesia.RateLimitError:
    # 429 — back off
except cartesia.AuthenticationError:
    # Bad API key
except cartesia.APIStatusError as e:
    # Other HTTP error
    print(e.status_code, e.response)
```

SDK automatically retries 2x on connection errors, 408, 429, and 5xx.

---

## 2. Claude Streaming API — With Tool Use

### Installed Version

Anthropic SDK **v0.85.0** (verified from local `.venv`).

### The Problem

Current `llm.py` uses `client.messages.create()` which returns a complete response. For TTS, we need to stream the final text response token-by-token so we can feed sentences to Cartesia as they form.

### Key Discovery: `stream.text_stream` + Tool Loop

Research into the Anthropic SDK v0.85.0 source (`_messages.py` line 288) revealed that `stream.text_stream` is an async iterator that **only yields `text_delta` events**, automatically skipping `input_json_delta` (tool input). This means we can stream **every** call in the tool loop — not just the final one.

**Why this matters for UX**: If Claude says "Let me look that up for you." before calling `search_handbook`, that text streams to TTS immediately. The parent hears it while the tool executes in the background.

### Streaming Event Types (from SDK source)

| Event Type | Delta Type | Yielded by `text_stream`? |
|---|---|---|
| `content_block_delta` + `text_delta` | Text token | Yes |
| `content_block_delta` + `input_json_delta` | Tool input JSON chunk | No (skipped) |
| `content_block_start` + `tool_use` | Tool call start | No |
| `message_delta` | `stop_reason` | No |

### Implementation Pattern

```python
async def chat_streaming(
    self,
    session_id: str,
    user_message: str,
) -> AsyncGenerator[dict, None]:
    """Streaming version of chat() that yields structured events for TTS + UI.

    Handles the tool_use loop internally:
      1. Stream Claude's response — text_stream yields only text deltas
      2. If stop_reason == "tool_use", execute tools silently
      3. Loop back — stream the follow-up response (text yielded here)
      4. If stop_reason == "end_turn", done

    Yields:
        {"type": "text_delta", "text": str}          — text token for TTS + UI
        {"type": "tool_call", "name": str}            — tool being executed (for status UI)
        {"type": "done",                              — stream complete
         "full_text": str,
         "citations": list[dict],
         "tool_used": str | None,
         "transferred": bool,
         "transfer_reason": str | None}
    """
    state = self.get_or_create_session(session_id)
    state.messages.append({"role": "user", "content": user_message})
    system_prompt = await self._build_system_prompt(state)

    citations: list[dict] = []
    tool_used: str | None = None
    transferred = False
    transfer_reason: str | None = None
    full_text = ""

    # Stream EVERY call — text_stream skips tool JSON automatically
    while True:
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=state.messages,
        ) as stream:
            # Yield text deltas as they arrive (pre-tool text + final text)
            async for text_chunk in stream.text_stream:
                full_text += text_chunk
                yield {"type": "text_delta", "text": text_chunk}

            # Get accumulated message to check stop_reason
            response = await stream.get_final_message()

        if response.stop_reason != "tool_use":
            # Done — final text has been fully streamed above
            state.messages.append({"role": "assistant", "content": full_text})
            if transferred:
                state.transferred = True
            yield {
                "type": "done",
                "full_text": full_text,
                "citations": citations,
                "tool_used": tool_used,
                "transferred": transferred,
                "transfer_reason": transfer_reason,
            }
            break

        # --- Tool execution (no text to stream during this phase) ---
        # Add assistant message with tool_use blocks to history
        # SDK auto-serializes the content block objects
        state.messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_used = block.name
                yield {"type": "tool_call", "name": block.name}

                result = await self._execute_tool(state, block.name, block.input)

                # Extract citations from handbook results
                if block.name == "search_handbook" and isinstance(result, list):
                    for chunk_data in result:
                        citations.append({
                            "page": chunk_data["page_number"],
                            "section": chunk_data["section_title"],
                            "text": chunk_data["text"][:200],
                        })

                # Track transfer_to_human
                if block.name == "transfer_to_human":
                    transferred = True
                    transfer_reason = block.input.get("reason", "Unknown")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result) if not isinstance(result, str) else result,
                })

        state.messages.append({"role": "user", "content": tool_results})
        # Loop back — next streaming call yields the post-tool text response
```

**Key insight from SDK source**: `stream.text_stream` (defined in `AsyncMessageStream.__stream_text__`) filters to only `content_block_delta` events where `delta.type == "text_delta"`. This means the same streaming loop handles both pre-tool text and post-tool text naturally. No need for a separate non-streaming tool phase.

**Edge cases handled**:
- **No pre-tool text**: `text_stream` yields nothing, `get_final_message()` returns immediately with `stop_reason="tool_use"`, tools execute, loop continues
- **Multiple tool calls**: All `tool_use` blocks appear in `response.content`, all executed, results sent back, loop continues
- **Pre-tool text exists**: "Let me look that up" streams to TTS, then tools execute silently, then post-tool answer streams

### `messages.stream()` API (from SDK source, line 2478 of messages.py)

```python
# Returns AsyncMessageStreamManager — use as async context manager
async with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    system="...",
    tools=[...],
    messages=[...],
) as stream:
    # Option 1: Just text deltas (RECOMMENDED for TTS)
    async for text in stream.text_stream:
        # text is a str — each token as it arrives
        # Automatically skips tool input JSON
        pass

    # Option 2: All parsed events (for monitoring tool calls)
    async for event in stream:
        if event.type == "text":
            # event.text = delta, event.snapshot = accumulated
            pass
        elif event.type == "content_block_start":
            if event.content_block.type == "tool_use":
                # Tool call starting — could show "Searching..." indicator
                pass

    # After iteration, get the accumulated message:
    final_message = await stream.get_final_message()
    # final_message.stop_reason: "end_turn" | "tool_use" | "max_tokens" | ...
    # final_message.content: list of TextBlock / ToolUseBlock objects

    # Also available during iteration:
    # stream.current_message_snapshot — accumulated message so far
```

---

## 3. Sentence Splitter — For TTS Pipeline

### IMPORTANT: Existing Code

`backend/app/services/cartesia_tts.py` ALREADY has:
- `split_into_sentences(text)` — batch sentence splitter (lines 74-120)
- `strip_markdown(text)` — removes markdown for clean TTS input (lines 31-71)
- `_ABBREVIATIONS` set — Dr, Mr, Mrs, Ms, Jr, Sr, Prof, St, Ave, vs, etc, i.e, e.g
- Tests in `backend/tests/test_tts.py` covering both functions

The existing `split_into_sentences()` works on **complete text** (batch mode). For streaming, we need a **stateful** `StreamingSentenceSplitter` class that accumulates tokens and yields sentences as they form. It should reuse the same abbreviation list and ellipsis handling.

### Requirements for the Streaming Variant

- Runs on every text delta from the LLM stream (must be fast)
- Reuse `_ABBREVIATIONS` and `_ends_with_abbreviation()` from existing code
- Applies `strip_markdown()` before splitting (or strips inline as tokens arrive)
- Batches short fragments (minimum ~30 chars before sending to TTS)
- New class: `StreamingSentenceSplitter` added to `cartesia_tts.py` (not a new file)

### Recommended Approach: Stateful class extending existing patterns

```python
import re

# Common abbreviations that end with a period but aren't sentence endings
ABBREVIATIONS = frozenset({
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "ave", "blvd",
    "dept", "est", "govt", "inc", "ltd", "mgr", "no", "rm", "vs",
    "approx", "appt", "ext", "misc", "mon", "tue", "wed", "thu", "fri",
    "sat", "sun", "jan", "feb", "mar", "apr", "jun", "jul", "aug",
    "sep", "oct", "nov", "dec", "a.m", "p.m",
})

# Minimum character count before yielding a sentence to TTS
MIN_CHUNK_LENGTH = 30


class SentenceSplitter:
    """Accumulates streaming text tokens and yields complete sentences."""

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
        sentences: list[str] = []

        while True:
            # Find potential sentence boundary
            match = re.search(r'([.!?])\s+', self._buffer)
            if not match:
                # Check for newline boundary
                newline_pos = self._buffer.find('\n')
                if newline_pos > 0:
                    candidate = self._buffer[:newline_pos].strip()
                    if len(candidate) >= self._min_length:
                        sentences.append(candidate)
                        self._buffer = self._buffer[newline_pos + 1:]
                        continue
                break

            pos = match.end()
            candidate = self._buffer[:pos].strip()

            # Check if the period is part of an abbreviation
            if match.group(1) == '.':
                # Get the word before the period
                words = candidate.rstrip('.').split()
                if words:
                    last_word = words[-1].lower().rstrip('.')
                    if last_word in ABBREVIATIONS:
                        # This is an abbreviation, not a sentence end
                        # Look for the next boundary instead
                        # Move past this match and keep searching
                        next_match = re.search(r'([.!?])\s+', self._buffer[pos:])
                        if not next_match:
                            break
                        pos = pos + next_match.end()
                        candidate = self._buffer[:pos].strip()

                # Check if it's a decimal number (e.g., 3.14, $125.00)
                if re.search(r'\d\.\d', candidate[-10:]):
                    break

            # Only yield if we have enough text
            if len(candidate) >= self._min_length:
                sentences.append(candidate)
                self._buffer = self._buffer[pos:]
            else:
                break

        return sentences
```

### Why Not a Library?

- `pysbd` (Python Sentence Boundary Disambiguation) is good but adds a dependency and is designed for batch processing, not streaming token-by-token.
- `nltk.tokenize.sent_tokenize` requires downloading punkt data and is overkill.
- A focused regex approach handles our specific use case (LLM output) with zero dependencies and microsecond performance.

---

## 4. Frontend Audio Playback — `GaplessAudioPlayer`

### Implementation (TypeScript)

```typescript
export class GaplessAudioPlayer {
  private audioContext: AudioContext;
  private nextPlaySample: number = 0;
  private startTimeSeconds: number = 0;
  private isPlaying: boolean = false;
  private activeSources: Set<AudioBufferSourceNode> = new Set();
  private sampleRate: number;
  private gainNode: GainNode;

  constructor(sampleRate: number = 24000) {
    this.sampleRate = sampleRate;
    this.audioContext = new AudioContext({ sampleRate });
    this.gainNode = this.audioContext.createGain();
    this.gainNode.connect(this.audioContext.destination);
  }

  async ensureResumed(): Promise<void> {
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }
  }

  enqueueChunk(pcm16Chunk: ArrayBuffer): void {
    const float32 = this.pcm16ToFloat32(pcm16Chunk);
    const audioBuffer = this.audioContext.createBuffer(1, float32.length, this.sampleRate);
    audioBuffer.getChannelData(0).set(float32);

    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.gainNode);

    this.activeSources.add(source);
    source.onended = () => {
      source.disconnect();
      this.activeSources.delete(source);
    };

    const currentTime = this.audioContext.currentTime;

    if (!this.isPlaying) {
      this.startTimeSeconds = currentTime + 0.01;
      this.nextPlaySample = 0;
      this.isPlaying = true;
    }

    // Track time in samples (integer) to avoid float drift
    const scheduledTime = this.startTimeSeconds + this.nextPlaySample / this.sampleRate;

    if (scheduledTime < currentTime) {
      this.startTimeSeconds = currentTime + 0.005;
      this.nextPlaySample = 0;
    }

    const finalTime = this.startTimeSeconds + this.nextPlaySample / this.sampleRate;
    source.start(finalTime);
    this.nextPlaySample += float32.length;
  }

  flush(): void {
    this.gainNode.gain.setValueAtTime(0, this.audioContext.currentTime);
    for (const source of this.activeSources) {
      try { source.stop(); source.disconnect(); } catch {}
    }
    this.activeSources.clear();
    this.gainNode.gain.setValueAtTime(1, this.audioContext.currentTime + 0.02);
    this.isPlaying = false;
    this.nextPlaySample = 0;
  }

  get playing(): boolean {
    return this.activeSources.size > 0;
  }

  async destroy(): Promise<void> {
    this.flush();
    await this.audioContext.close();
  }

  private pcm16ToFloat32(pcm16: ArrayBuffer): Float32Array {
    const int16 = new Int16Array(pcm16);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768;
    }
    return float32;
  }
}
```

### Key Design Decisions

- **Sample-based timing**: Track `nextPlaySample` as an integer to prevent floating-point drift between chunks.
- **GainNode for barge-in**: Setting gain to 0 instantly silences without pops, then `source.stop()` cleans up.
- **24kHz sample rate**: Matches Cartesia output. AudioContext is created at 24000Hz to avoid resampling.
- **PCM16 wire format**: Half the bandwidth of Float32, trivial conversion.
- **AutoPlay policy**: `ensureResumed()` must be called from a user gesture (button click).

---

## 5. Full Integration Plan — File-by-File Changes

### New Files

| File | Purpose |
|---|---|
| `frontend/src/services/audioPlayer.ts` | GaplessAudioPlayer — PCM chunk playback |
| `frontend/src/hooks/useAudio.ts` | React hook wrapping GaplessAudioPlayer |

### Modified Files

| File | Changes |
|---|---|
| `backend/app/services/cartesia_tts.py` | **REFACTOR** existing `CartesiaTTSService`: add Cartesia WebSocket SDK integration in `_synthesize_sentence()`, add `StreamingSentenceSplitter` class for token-by-token splitting, update `model_id` default from `sonic-2024-12-12` to `sonic-3`. Keep existing `strip_markdown()`, `split_into_sentences()`, `_ABBREVIATIONS` — they are tested and correct. Add `connect()` for WebSocket lifecycle, `cancel_utterance()` for barge-in, and a streaming `read_response_streaming()` method that accepts an `AsyncGenerator` of text deltas instead of complete text. |
| `backend/app/services/llm.py` | Add `chat_streaming()` method (yields `dict` events: `text_delta`, `tool_call`, `done` with full metadata including `transferred`/`transfer_reason`) |
| `backend/app/api/websocket.py` | Replace `llm_service.chat()` + `tts_service.read_response()` in `process_utterance()` with streaming pipeline: `chat_streaming()` → `StreamingSentenceSplitter` → `tts_service`. Add `tts_interrupt` handler in the receive loop (see Section 6b). Send `response_delta` JSON messages for progressive text display. Handle concurrency between background `process_utterance` task and interrupt signals. |
| `backend/app/main.py` | Call `await tts_service.connect()` during lifespan startup (after constructing `CartesiaTTSService`). No structural changes — already creates and stores `tts_service` on `app.state`. |
| `backend/app/config.py` | Already has `cartesia_api_key` and `cartesia_voice_id` — no changes needed |
| `frontend/src/hooks/useVoice.ts` | Handle binary WebSocket frames (audio), `tts_start`/`tts_end` messages, `response_delta` for streaming text, barge-in via `tts_interrupt` |
| `pyproject.toml` | Add `cartesia[websockets]` dependency |
| `backend/tests/test_tts.py` | Add tests for `StreamingSentenceSplitter`, updated `CartesiaTTSService` with mock WebSocket SDK |

### Dependency Addition

```toml
# In pyproject.toml [project.dependencies]
"cartesia[websockets]>=3.0.0",
```

---

## 6. Backend Pipeline — How the Pieces Connect

```
┌──────────────────────────────────────────────────────────────────────┐
│                  websocket.py — process_utterance()                   │
│                                                                       │
│  1. User speaks → Deepgram → transcript                               │
│                                                                       │
│  2. llm_service.chat_streaming(session_id, text)                      │
│     while True:                                                       │
│       ├── messages.stream() — text_stream yields text_delta events    │
│       │   (skips tool input JSON; yields pre-tool text like           │
│       │    "Let me look that up" as well as post-tool answer)         │
│       ├── get_final_message() → check stop_reason                     │
│       ├── if "tool_use": execute tools silently, loop back            │
│       └── if "end_turn": yield done event, break                      │
│                                                                       │
│  3. For each text_delta event:                                        │
│     ├── Send to browser: {"type": "response_delta", "text": …}       │
│     └── streaming_splitter.push(delta.text)                           │
│         └── If complete sentence returned:                            │
│             └── await tts_service.push_sentence(sentence)             │
│                                                                       │
│  4. On done event:                                                    │
│     ├── streaming_splitter.flush() → push remainder to TTS            │
│     ├── await tts_service.finish_utterance()                          │
│     ├── Send full {"type": "response", ...} with metadata             │
│     └── Save to DB (citations, tool_used, transferred, etc.)          │
│                                                                       │
│  5. Concurrent: tts_service receive loop → audio chunks               │
│     └── websocket.send_bytes(chunk) → browser AudioContext            │
│                                                                       │
│  BARGE-IN: If {"type": "tts_interrupt"} arrives in receive loop:      │
│     ├── Set cancellation flag (asyncio.Event)                         │
│     └── process_utterance checks flag → calls tts_service.cancel()    │
└──────────────────────────────────────────────────────────────────────┘
```

### Refactored CartesiaTTSService (in existing `cartesia_tts.py`)

The existing `CartesiaTTSService` is refactored to add WebSocket lifecycle and streaming support. The class stays in `cartesia_tts.py` — no new file.

```python
# Additions to existing CartesiaTTSService class:

class CartesiaTTSService:
    """Manages TTS synthesis via Cartesia.

    EXISTING (keep):
      - __init__, _api_key, _voice_id, _model_id
      - read_response() — batch mode for complete text (used by text chat)
      - _synthesize_sentence() — single sentence synthesis
      - close()

    NEW (add for streaming voice pipeline):
      - connect() — open persistent Cartesia WebSocket
      - start_utterance() — create a new Cartesia context
      - push_sentence(text) — push sentence to active context
      - finish_utterance() — signal no more text, wait for audio drain
      - cancel_utterance() — barge-in cancellation
      - _receive_loop() — background task forwarding audio chunks
    """

    async def start_utterance(self) -> None:
        """Create a new context for a new assistant response."""
        self._current_ctx = self._connection.context(
            model_id="sonic-3",
            voice={"mode": "id", "id": self._voice_id},
            output_format={
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 24000,
            },
        )
        # Start receiving audio chunks in background
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def push_sentence(self, text: str) -> None:
        """Push a sentence to Cartesia for synthesis. MUST await."""
        if self._current_ctx:
            await self._current_ctx.push(text)

    async def finish_utterance(self) -> None:
        """Signal no more text for this utterance. MUST await."""
        if self._current_ctx:
            await self._current_ctx.no_more_inputs()
        # Wait for all audio to be received
        if self._receive_task:
            await self._receive_task

    async def cancel_utterance(self) -> None:
        """Cancel current synthesis (barge-in)."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        self._current_ctx = None

    async def _receive_loop(self) -> None:
        """Receive audio chunks and forward via callback."""
        try:
            if self._current_ctx:
                async for response in self._current_ctx.receive():
                    if response.type == "chunk" and response.audio:
                        await self._on_audio_chunk(response.audio)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error receiving Cartesia audio")

    async def close(self) -> None:
        """Gracefully close the Cartesia connection."""
        await self.cancel_utterance()
        if self._ws_ctx:
            try:
                await self._ws_ctx.__aexit__(None, None, None)
            except Exception:
                pass
```

### 6b. Backend `tts_interrupt` Handler — Concurrency Design

The `tts_interrupt` message arrives in the main receive loop, but `process_utterance()` runs as a background `asyncio.Task`. These need to coordinate:

```python
# In voice_websocket():
tts_cancel_event = asyncio.Event()  # shared between receive loop and process_utterance

# In the receive loop, add a new branch:
if msg.get("type") == "tts_interrupt":
    tts_cancel_event.set()  # signal the background task to stop TTS
    logger.info("TTS interrupted by user (session: %s)", session_id)

# In process_utterance(), check the event:
async def process_utterance(text: str) -> None:
    nonlocal tts_cancel_event
    ...
    # After starting TTS streaming:
    for sentence in sentences:
        if tts_cancel_event.is_set():
            await tts_service.cancel_utterance()
            break
        await tts_service.push_sentence(sentence)
    ...
    # Reset for next utterance
    tts_cancel_event.clear()
```

This works because both the receive loop and the background task run on the same asyncio event loop. The `asyncio.Event` is the standard coordination primitive for this pattern.

---

## 7. WebSocket Protocol Additions

### Server → Client (new message types)

```json
{"type": "response_delta", "text": "Welcome to "}
{"type": "response_delta", "text": "Sunshine Learning Center."}
{"type": "tts_start"}
// ... binary frames (raw PCM16 audio chunks) ...
{"type": "tts_end"}
{"type": "response", "text": "full text", "citations": [...]}
```

### Client → Server (new message type)

```json
{"type": "tts_interrupt"}
```

### Binary Frames

Server sends raw PCM16 audio as binary WebSocket frames. The client distinguishes binary from text frames automatically (`event.data instanceof ArrayBuffer`).

---

## 8. Frontend Hook Changes

### `useVoice.ts` Updates

```typescript
// In ws.onmessage:
ws.onmessage = (event) => {
  if (event.data instanceof ArrayBuffer) {
    // Binary frame = TTS audio chunk
    audioPlayer.enqueueChunk(event.data);
    return;
  }

  const data = JSON.parse(event.data) as ServerEvent;

  if (data.type === 'response_delta') {
    // Streaming text — update UI progressively
    onResponseDelta(data.text);
  } else if (data.type === 'tts_start') {
    setState('speaking');
  } else if (data.type === 'tts_end') {
    setState('listening');
  } else if (data.type === 'transcript') {
    // Existing transcript handling...
    if (data.is_final) {
      // User started speaking — barge in if TTS is playing
      if (audioPlayer.playing) {
        audioPlayer.flush();
        ws.send(JSON.stringify({ type: 'tts_interrupt' }));
      }
    }
  }
  // ... existing handlers
};
```

### `useAudio.ts` Hook

```typescript
import { useRef, useCallback } from 'react';
import { GaplessAudioPlayer } from '@/services/audioPlayer';

export function useAudio(sampleRate: number = 24000) {
  const playerRef = useRef<GaplessAudioPlayer | null>(null);

  const getPlayer = useCallback(() => {
    if (!playerRef.current) {
      playerRef.current = new GaplessAudioPlayer(sampleRate);
    }
    return playerRef.current;
  }, [sampleRate]);

  const ensureResumed = useCallback(async () => {
    await getPlayer().ensureResumed();
  }, [getPlayer]);

  const enqueueChunk = useCallback((chunk: ArrayBuffer) => {
    getPlayer().enqueueChunk(chunk);
  }, [getPlayer]);

  const flush = useCallback(() => {
    getPlayer().flush();
  }, [getPlayer]);

  const destroy = useCallback(async () => {
    if (playerRef.current) {
      await playerRef.current.destroy();
      playerRef.current = null;
    }
  }, []);

  return { ensureResumed, enqueueChunk, flush, destroy, getPlayer };
}
```

---

## 9. TDD Test Plan

### Tests to Write FIRST (before implementation)

#### `backend/tests/test_tts.py` (extend existing file)

NOTE: `test_tts.py` already has `TestStripMarkdown` (11 tests) and `TestSplitIntoSentences` (10 tests) and `TestCartesiaTTSService` (9 tests). Add a new test class:

```python
class TestStreamingSentenceSplitter:
    """Tests for the stateful streaming sentence splitter."""

    # Basic splitting
    def test_splits_on_period(self):
        s = StreamingSentenceSplitter(min_length=10)
        result = s.push("Hello world. How are you? ")
        assert result == ["Hello world."]

    def test_splits_on_question_mark(self): ...
    def test_splits_on_exclamation(self): ...
    def test_splits_on_newline(self): ...

    # Edge cases — reuses _ABBREVIATIONS from cartesia_tts.py
    def test_preserves_abbreviation_dr(self):
        s = StreamingSentenceSplitter(min_length=10)
        result = s.push("Dr. Martinez will see you. ")
        assert result == ["Dr. Martinez will see you."]

    def test_preserves_abbreviation_mrs(self): ...
    def test_preserves_decimal_number(self): ...
    def test_preserves_ellipsis(self): ...

    # Batching
    def test_batches_short_sentences(self):
        s = StreamingSentenceSplitter(min_length=30)
        result = s.push("Hi. ")
        assert result == []  # too short

    def test_flush_returns_remainder(self): ...

# Streaming simulation
def test_token_by_token():
    s = SentenceSplitter(min_length=10)
    sentences = []
    for char in "Hello world. How are you? Fine thanks. ":
        sentences.extend(s.push(char))
    remaining = s.flush()
    # Should have captured complete sentences
```

#### `backend/tests/test_tts.py` — extend `TestCartesiaTTSService`

```python
# Add to existing TestCartesiaTTSService class:

# Mock-based tests for new WebSocket methods (no real Cartesia API)
async def test_connect_creates_websocket(): ...
async def test_push_sentence_awaits_ctx_push(): ...
async def test_finish_utterance_awaits_no_more_inputs(): ...
async def test_cancel_stops_receive_loop(): ...
async def test_audio_chunks_forwarded_via_callback(): ...
async def test_close_cleans_up_resources(): ...
```

#### `backend/tests/test_llm_streaming.py`

```python
# Test the streaming chat method
async def test_chat_streaming_yields_text_deltas(): ...
async def test_chat_streaming_handles_tool_calls(): ...
async def test_chat_streaming_yields_citations(): ...
async def test_chat_streaming_yields_done_event(): ...
```

#### `frontend/src/services/__tests__/audioPlayer.test.ts`

```typescript
// Using a mock AudioContext
test('enqueueChunk converts PCM16 to Float32', () => { ... });
test('flush stops all active sources', () => { ... });
test('playing returns false when no sources active', () => { ... });
test('ensureResumed calls audioContext.resume', () => { ... });
```

---

## 10. Implementation Order

1. **`pyproject.toml`** — Add `cartesia[websockets]>=3.0.0` dependency, `uv lock`
2. **`cartesia_tts.py` — `StreamingSentenceSplitter`** + tests in `test_tts.py` — Pure stateful class, no SDK, test first
3. **`cartesia_tts.py` — WebSocket SDK integration** + tests — Add `connect()`, `start_utterance()`, `push_sentence()`, `finish_utterance()`, `cancel_utterance()`, `_receive_loop()`. Update `model_id` default to `sonic-3`. Mock-tested.
4. **`llm.py` — `chat_streaming()`** + tests — Add streaming method alongside existing `chat()`. Returns `AsyncGenerator[dict, None]` with structured events.
5. **`websocket.py` — streaming pipeline** — Replace `llm_service.chat()` + `tts_service.read_response()` with `chat_streaming()` → `StreamingSentenceSplitter` → `tts_service`. Add `tts_interrupt` handler with `asyncio.Event` coordination.
6. **`main.py` lifespan** — Add `await tts_service.connect()` in startup
7. **`audioPlayer.ts`** + tests — Frontend `GaplessAudioPlayer`
8. **`useAudio.ts` hook** — React wrapper
9. **`useVoice.ts` updates** — Handle binary frames, `response_delta`, `tts_start`/`tts_end`, barge-in
10. **End-to-end test** — Full voice → transcript → LLM → TTS → audio playback

### What DOESN'T Change

- `config.py` — Already has `cartesia_api_key` and `cartesia_voice_id`
- `POST /api/chat` — Text chat remains non-streaming (TTS is voice-only). The existing batch `read_response()` stays available if text chat ever needs TTS.
- `deepgram_session.py` — Untouched
- Handbook RAG, database, seed data — All untouched
- Operator dashboard — Untouched
- `strip_markdown()`, `split_into_sentences()` — Keep as-is, already tested

---

## 11. Open Questions

1. **Should `POST /api/chat` also support TTS?** The plan assumes TTS is voice-mode only (WebSocket). The existing batch `CartesiaTTSService.read_response()` is kept for this scenario but is not wired to the text chat endpoint. If text-mode chat should also speak responses, we need SSE or a separate TTS endpoint.

2. **Audio toggle UI** — The websocket handler already reads `tts_enabled` and `tts_speed` from the config message (lines 191-192 of `websocket.py`). Where does the UI toggle live? Header? Settings menu? This is a frontend design question.

3. **Cartesia connection lifecycle** — Current plan: one `CartesiaTTSService` per app (singleton on `app.state`), with one persistent WebSocket connection opened at startup via `connect()`. Multiple concurrent utterances (from different browser sessions) create separate contexts on the same WebSocket. This is how Cartesia recommends using their SDK for scale (see `tts_async_concurrent_contexts` example).
