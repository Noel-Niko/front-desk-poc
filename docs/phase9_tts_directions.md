# Phase 9 TTS Directions — For the LLM updating implementation_plan.md

## Decision Made

**We are using Cartesia WebSocket with sentence splitting — NOT `tts.bytes()`.**

`tts.bytes()` is the REST Bytes endpoint that waits for the entire text to be synthesized before returning any audio. This is unacceptable for a conversational voice assistant because the user would wait for the full LLM response + full TTS synthesis before hearing anything.

## What you should update in Phase 9

Rewrite the Phase 9 task list to reflect this architecture:

### The pipeline

```
LLM streams tokens
       │
       ▼
Sentence buffer (accumulate tokens until sentence boundary: . ? ! \n)
       │
       ▼
Send completed sentence to Cartesia WebSocket (using continuations)
       │
       ▼
Cartesia streams audio chunks back immediately
       │
       ▼
Forward audio chunks over the existing browser WebSocket as binary frames
       │
       ▼
Browser AudioContext plays chunks as they arrive
```

### Key architectural points to capture in the plan

1. **Backend: `CartesiaSession` service** (new file, similar pattern to `DeepgramSession`)
   - Manages a persistent WebSocket connection to Cartesia
   - One session per browser WebSocket connection (same lifecycle as `DeepgramSession`)
   - Uses Cartesia's **continuation** feature: each sentence is sent as a continuation within the same context, so prosody flows naturally across sentences
   - Uses **context flushing** to signal end of each sentence chunk

2. **Backend: Sentence splitter utility**
   - Splits LLM streaming output on sentence boundaries (`. ` `? ` `! ` and newlines)
   - Buffers tokens until a boundary is detected, then yields the complete sentence
   - Must handle edge cases: abbreviations (Dr., Mrs., etc.), ellipsis (...), numbered lists

3. **Backend: LLM streaming integration**
   - Currently `llm.py` returns a complete response. It needs a streaming variant that yields tokens as they arrive from Claude
   - As tokens stream in, they feed the sentence splitter
   - Each completed sentence is sent to the `CartesiaSession`
   - Audio chunks from Cartesia are forwarded to the browser as binary WebSocket frames

4. **Frontend: Audio playback**
   - Receive binary WebSocket frames (PCM16 or WAV audio chunks)
   - Queue chunks into a Web Audio API `AudioContext` for gapless playback
   - Must handle: chunk queuing, playback state (playing/idle), interruption (user starts speaking mid-playback → stop TTS)

5. **Frontend: Barge-in / interruption**
   - If user starts speaking while TTS is playing, immediately:
     - Stop audio playback on the frontend
     - Send a cancel/flush signal to backend
     - Backend closes the current Cartesia context

6. **WebSocket protocol additions**
   - Server → Client: binary frames = raw audio chunks from Cartesia
   - Server → Client: `{"type": "tts_start"}` — audio is about to begin
   - Server → Client: `{"type": "tts_end"}` — all audio for this response is done
   - Client → Server: `{"type": "tts_interrupt"}` — user interrupted, stop playback

7. **Config** — already has `cartesia_api_key` and `cartesia_voice_id` in `config.py`

8. **Toggle** — user can switch between: text only / audio only / both

### What NOT to include

- Do NOT reference `tts.bytes()` or the REST Bytes endpoint — that approach is rejected
- Do NOT reference `tts.sse()` — we are using WebSocket, not SSE
- Remove or replace the line about "Sentence-level progressive synthesis" with the full pipeline description above

## Division of work

**A separate research agent is investigating the Cartesia WebSocket SDK implementation details.** This includes:
- Exact Cartesia Python SDK methods for WebSocket connections
- Continuation and context flushing API
- Audio format parameters (encoding, sample rate, container)
- Error handling and reconnection patterns
- Any SDK quirks (similar to the Deepgram SDK issues we hit)

**You should NOT block on this research.** Proceed with:
- Updating the Phase 9 task list in `implementation_plan.md` with the architecture above
- Writing TDD tests for the components that don't depend on SDK specifics:
  - Sentence splitter (pure function — given a stream of tokens, yields sentences)
  - WebSocket protocol additions (new message types)
  - Audio toggle state management
  - Barge-in/interruption logic
- Writing TDD tests for the other pending phases (5, 6, 7, 8, 10)
- Any other pending tasks

**The research agent will deliver** a separate doc (`docs/cartesia_ws_research.md`) with:
- Exact SDK code patterns for CartesiaSession
- Working connection/send/receive examples
- Audio format recommendations
- Edge cases and pitfalls

You will integrate those findings when they're available. Do not guess at SDK method names or signatures — use placeholder comments like `# TODO: integrate Cartesia SDK (see docs/cartesia_ws_research.md)` where needed.

## Reference: existing patterns to follow

- `backend/app/services/deepgram_session.py` — The `DeepgramSession` class is the model for `CartesiaSession`. Same lifecycle pattern: init → connect → send data → receive events → graceful shutdown.
- `backend/app/api/websocket.py` — The existing voice WebSocket handler manages a `DeepgramSession`. It will need to also manage a `CartesiaSession` and coordinate between them.
- `backend/app/services/llm.py` — Currently returns complete responses. Needs a streaming variant for the TTS pipeline.
