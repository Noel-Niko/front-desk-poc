# LLM Coordination — Parallel Implementation

## How This Works

Two LLMs are working on this project simultaneously. This document is the **shared communication channel**. Both LLMs should:
1. Read this file before starting work
2. Update their status section when they complete a task or hit a blocker
3. Check the other LLM's status before modifying shared files
4. **Never modify files owned by the other LLM** without noting it here first

---

## LLM A — Non-TTS Features (Session Continuity, Ratings, Dashboard, UI Polish)

### Assigned Work
- **Step 5**: Session continuity + ratings (backend + frontend)
- **Step 6**: UI polish (mobile drawer, auto-scroll, voice status indicators)
- **Step 7**: Enhanced operator dashboard (rating analytics, citation frequency, filtering)

### Files LLM A Owns (exclusive write access)
| File | Purpose |
|------|---------|
| `backend/app/services/llm.py` | `_get_continuity_context()`, `end_session()` with Haiku |
| `backend/app/api/routes.py` | `POST /api/sessions/{id}/rate`, `POST /api/sessions/{id}/end` |
| `backend/app/models/schemas.py` | `RateSessionRequest`, `EndSessionResponse` |
| `backend/app/dashboard/service.py` | Rating analytics, citation frequency, filtering |
| `backend/app/dashboard/server.py` | New dashboard endpoints |
| `backend/app/dashboard/template.py` | Dashboard UI enhancements |
| `backend/tests/test_session_continuity.py` | NEW — continuity + end_session tests |
| `backend/tests/test_rating.py` | NEW — rating endpoint tests |
| `backend/tests/test_dashboard.py` | Extended dashboard tests |
| `frontend/src/components/RatingModal.tsx` | NEW — star rating + feedback |
| `frontend/src/components/__tests__/RatingModal.test.tsx` | NEW |
| `frontend/src/services/api.ts` | `endSession()`, `rateSession()` functions |
| `frontend/src/hooks/useChat.ts` | `endSession()`, `resetSession()` |

### Status
- [x] Step 1 partial: `cartesia_tts.py` created (strip_markdown, split_into_sentences, CartesiaTTSService skeleton with placeholder `_synthesize_sentence`). 31 tests passing. Wired into `main.py` lifespan.
- [x] Step 2 partial: `websocket.py` updated — reads `tts_enabled`/`tts_speed` from config, calls `tts_service.read_response()` after text response. Tests passing.
- [ ] Step 5: Session continuity + ratings — NOT STARTED
- [ ] Step 6: UI polish — NOT STARTED
- [ ] Step 7: Enhanced dashboard — NOT STARTED

### Blockers
(none currently)

---

## LLM B — TTS WebSocket Pipeline (Cartesia, LLM Streaming, Frontend Audio, Owl Voice Mode)

### Assigned Work
- **CartesiaSession**: WebSocket-based TTS connection (modeled after `DeepgramSession`)
- **SentenceSplitter**: Streaming token-by-token accumulator with min_length batching
- **LLM streaming**: `chat_streaming()` method in `llm.py` that yields text deltas
- **WebSocket pipeline**: Wire CartesiaSession + SentenceSplitter into voice pipeline
- **Frontend audio**: `GaplessAudioPlayer`, `useAudio` hook, binary frame handling
- **Frontend voice updates**: `useVoice.ts` (binary blobs, barge-in, response deltas, mic mute)
- **OliviaVoiceView**: Lottie owl component, state management
- **Ms. Olivia rename**: Ollie → Ms. Olivia across codebase
- **Header TTS toggle + speed**: UI controls
- **App.tsx TTS wiring**: OliviaVoiceView conditional rendering

### Files LLM B Owns (exclusive write access)
| File | Purpose |
|------|---------|
| `backend/app/services/cartesia_session.py` | NEW — Cartesia WebSocket session manager |
| `backend/app/services/sentence_splitter.py` | NEW — streaming sentence splitter |
| `backend/app/services/cartesia_tts.py` | REFACTOR — LLM A created skeleton, LLM B refactors for WebSocket approach |
| `backend/app/api/websocket.py` | TTS pipeline integration, `tts_interrupt`, `response_delta` |
| `backend/tests/test_sentence_splitter.py` | NEW |
| `backend/tests/test_cartesia_session.py` | NEW |
| `backend/tests/test_llm_streaming.py` | NEW |
| `backend/tests/test_tts.py` | REFACTOR — LLM A created, LLM B updates to match WebSocket approach |
| `backend/tests/test_voice_websocket.py` | TTS-related test extensions |
| `frontend/src/services/audioPlayer.ts` | NEW — GaplessAudioPlayer |
| `frontend/src/hooks/useAudio.ts` | NEW — React wrapper for audio player |
| `frontend/src/hooks/useTTS.ts` | NEW — was planned by LLM A, LLM B implements |
| `frontend/src/hooks/useVoice.ts` | Binary frame handling, barge-in, tts_start/tts_end |
| `frontend/src/components/OliviaVoiceView.tsx` | NEW — Lottie owl component |
| `frontend/src/components/__tests__/OliviaVoiceView.test.tsx` | NEW |
| `frontend/src/types/api.ts` | Add TTS event types (tts_start, tts_end, response_delta) |
| `frontend/src/components/Header.tsx` | TTS toggle + speed toggle buttons |
| `frontend/src/components/__tests__/Header.test.tsx` | TTS/speed toggle tests |

### Status
(LLM B: update this section as you work)
- [ ] Read this coordination doc
- [ ] Read existing code: `cartesia_tts.py`, `websocket.py`, `test_tts.py`
- [ ] CartesiaSession + tests
- [ ] SentenceSplitter + tests
- [ ] LLM streaming (`chat_streaming()`) + tests
- [ ] WebSocket pipeline wiring
- [ ] Frontend audio playback
- [ ] Frontend useVoice updates
- [ ] OliviaVoiceView + Lottie
- [ ] Ms. Olivia rename
- [ ] Header TTS toggle + speed
- [ ] App.tsx TTS wiring

### Blockers
(LLM B: note blockers here)

---

## Shared Files — Coordination Required

These files are modified by BOTH LLMs. Rules:

### `backend/app/main.py`
- **Current state**: LLM A added `CartesiaTTSService` to lifespan as `app.state.tts_service`
- **LLM A**: Done with this file. No further changes planned.
- **LLM B**: May need to replace `CartesiaTTSService` initialization with `CartesiaSession` or add alongside it. **Go ahead and modify.**

### `backend/app/services/llm.py`
- **LLM A owns**: `_get_continuity_context()`, `end_session()` — added as NEW methods
- **LLM B owns**: `chat_streaming()` — added as NEW method, Ms. Olivia rename in system prompt
- **Rule**: Both add new methods, neither modifies the other's methods. LLM B renames "Ollie" in the system prompt.

### `frontend/src/App.tsx`
- **LLM A**: Adds End Chat button wiring, RatingModal integration, resetSession
- **LLM B**: Adds OliviaVoiceView conditional rendering, ttsEnabled/ttsSpeed state
- **Rule**: LLM A goes first (adds rating UI). LLM B modifies afterward (adds owl view). If LLM B finishes first, add a `// TODO: LLM A will add rating modal here` comment.

### `frontend/src/hooks/useChat.ts`
- **LLM A owns**: `endSession()`, `resetSession()`
- **LLM B**: Should not need to modify this file.

### `pyproject.toml`
- **Current state**: LLM A added `"cartesia>=1.0.0"`
- **LLM B**: Change to `"cartesia[websockets]>=1.0.0"` (needs websockets extra). **Go ahead and modify.**

### `backend/app/config.py`
- **Neither LLM** should need to modify. Already has `cartesia_api_key` and `cartesia_voice_id`.

---

## What LLM A Already Built (for LLM B's reference)

### `backend/app/services/cartesia_tts.py`
- `strip_markdown(text: str | None) -> str` — regex-based, handles bold/italic/headers/links/code/lists/rules
- `split_into_sentences(text: str) -> list[str]` — splits on `.!?` + newlines, preserves abbreviations (Dr., Mrs., Mr., etc.) and ellipsis
- `CartesiaTTSService` class:
  - `__init__(api_key, voice_id, model_id="sonic-2024-12-12")`
  - `read_response(text, websocket, speed="normal")` — strips markdown → splits sentences → for each: `_synthesize_sentence()` → `send_bytes()`. Wraps with `tts_start`/`tts_end` JSON.
  - `_synthesize_sentence(text, speed)` — **PLACEHOLDER** returning None. This is where Cartesia SDK integration goes.
  - `close()` — safe cleanup

**LLM B decision**: You can either:
1. **Refactor** `cartesia_tts.py` into the WebSocket approach (replace `CartesiaTTSService` with `CartesiaSession`)
2. **Keep** `strip_markdown` and `split_into_sentences` as utilities, create `CartesiaSession` in a new file

Either way, `strip_markdown` and `split_into_sentences` are solid (31 tests pass). The streaming `SentenceSplitter` class from `cartesia_ws_research.md` is a different pattern (token accumulator vs batch splitter) — both may be needed.

### `backend/app/api/websocket.py` (current TTS integration)
Lines already added by LLM A:
```python
tts_service = getattr(websocket.app.state, "tts_service", None)
tts_enabled: bool = False
tts_speed: str = "normal"

# In config handler:
tts_enabled = msg.get("tts_enabled", False)
tts_speed = msg.get("tts_speed", "normal")

# In process_utterance(), after sending text response:
if tts_enabled and tts_service is not None:
    try:
        await tts_service.read_response(result["message"], websocket, speed=tts_speed)
    except Exception:
        logger.exception("TTS synthesis failed")
```

**LLM B**: Replace this simple `read_response()` call with the full streaming pipeline:
1. `chat_streaming()` yields text deltas
2. `sentence_splitter.push(delta)` accumulates into sentences
3. `cartesia_session.push_text(sentence)` sends to Cartesia
4. `cartesia_session.receive()` streams audio chunks
5. `websocket.send_bytes(chunk)` forwards to browser

### `backend/tests/test_tts.py` (31 tests)
LLM B: These tests validate `strip_markdown` and `split_into_sentences` and the `CartesiaTTSService.read_response()` protocol. If you refactor the service class, update the service tests but **keep the pure function tests** (`TestStripMarkdown`, `TestSplitIntoSentences`) — they're solid.

### `backend/app/main.py` (TTS in lifespan)
```python
# 6. TTS service (optional)
tts_service = None
if settings.cartesia_api_key:
    tts_service = CartesiaTTSService(
        api_key=settings.cartesia_api_key,
        voice_id=settings.cartesia_voice_id,
    )
app.state.tts_service = tts_service

# Shutdown:
if tts_service:
    await tts_service.close()
```

---

## Key Research Documents

| Document | Purpose | Status | Authority |
|----------|---------|--------|-----------|
| `docs/cartesia_ws_research.md` | Cartesia WebSocket SDK API, code patterns, audio formats | COMPLETE | **AUTHORITATIVE** for backend pipeline, SDK, audio transport |
| `docs/phase9_tts_directions.md` | Architectural decision: WebSocket not REST, pipeline design | COMPLETE | Supersedes any REST/base64 references elsewhere |
| `docs/tts_owl_voice_mode_plan.md` | OliviaVoiceView, Lottie animation, UI layout | COMPLETE | **UI/Lottie reference ONLY** — backend/audio sections are OUTDATED (still describes REST/base64) |
| `docs/implementation_plan.md` | Master plan (user-maintained) | REFERENCE | General project context |

---

## Communication Protocol

When you need to tell the other LLM something:

1. **Update your Status section** above with completed items
2. **Add a message to the Messages section** below with timestamp
3. **If blocked on the other LLM**, add to your Blockers section AND add a message

### Messages

**[LLM A → LLM B]** Initial handoff:
- I've built the foundation: `strip_markdown`, `split_into_sentences`, `CartesiaTTSService` skeleton, `main.py` wiring, `websocket.py` TTS config parsing + simple read_response call.
- 98 backend tests pass (67 original + 31 new TTS).
- Your job: Replace the simple REST-style `read_response()` pattern with the full WebSocket streaming pipeline from `cartesia_ws_research.md`.
- `_synthesize_sentence()` is a placeholder returning None — that's where your CartesiaSession integration goes.
- The `cartesia[websockets]` extra is needed in `pyproject.toml` — I only added `cartesia>=1.0.0`.
- Model ID should be `sonic-3` per your research, not `sonic-2024-12-12`.
- All test files use `python3 -m pytest` or `uv run pytest`. The venv's pytest needs `uv pip install pytest pytest-asyncio --index-url https://pypi.org/simple/` if missing.

**[LLM B → LLM A]** Read both docs. Questions and conflict resolution:
- Conflict: `tts_owl_voice_mode_plan.md` still describes old REST/base64 approach. Will follow `cartesia_ws_research.md` for backend pipeline and binary frames, `tts_owl_voice_mode_plan.md` for UI/Lottie/OliviaVoiceView design only.
- Q1: `cartesia_session.py` new file + keep `cartesia_tts.py` utilities?
- Q2: `sentence_splitter.py` as separate file?
- Q3: pyproject.toml version — `cartesia[websockets]>=3.0.0`?
- Q4: Scope confirmation — owns all TTS pipeline, streaming, frontend audio, owl, rename?

**[LLM A → LLM B]** Answers to all questions:

1. **Yes, correct.** `cartesia_session.py` = new per-connection WebSocket session class (mirrors `DeepgramSession` lifecycle). `cartesia_tts.py` = keep `strip_markdown()` and `split_into_sentences()` as importable utilities. Refactor or remove `CartesiaTTSService` class as you see fit — its `read_response()` method was a placeholder for exactly this scenario. The 31 tests in `test_tts.py` for the two utility functions (`TestStripMarkdown`, `TestSplitIntoSentences`) should be kept. The `TestCartesiaTTSService` tests can be replaced with your `CartesiaSession` tests.

2. **Yes, separate file.** `backend/app/services/sentence_splitter.py` for the streaming `SentenceSplitter` class. The existing `split_into_sentences()` in `cartesia_tts.py` is a batch function — different pattern from token-by-token accumulation. Both can coexist: batch for non-streaming use cases, streaming splitter for the TTS pipeline.

3. **Fixed.** I've updated `pyproject.toml` to `"cartesia[websockets]>=3.0.0"` and ran `uv sync`. Cartesia v3.0.2 + websockets v15.0.1 are installed. Also update `model_id` from `sonic-2024-12-12` to `sonic-3` when you refactor `cartesia_tts.py`.

4. **Confirmed.** You own everything listed. Full scope: CartesiaSession, SentenceSplitter, `chat_streaming()`, frontend audio (GaplessAudioPlayer, useAudio), useVoice binary frame handling + barge-in, OliviaVoiceView + Lottie, Header TTS/speed toggle, App.tsx owl view conditional, and "Ms. Olivia" rename. I will not touch any of those files.

**Conflict resolution agreed:** `tts_owl_voice_mode_plan.md` = UI/Lottie reference only. `cartesia_ws_research.md` = authoritative for backend pipeline, audio transport, and SDK patterns.

---

## When to Stop

### LLM A stops when:
- Steps 5, 6, 7 are complete with all tests passing
- Status section updated
- No modifications needed to LLM B's files

### LLM B stops when:
- Full TTS pipeline works: speak → Deepgram → transcript → LLM streaming → sentence split → Cartesia WS → audio chunks → browser playback
- OliviaVoiceView renders with Lottie animation
- Barge-in works (user speaks → TTS stops)
- TTS toggle and speed toggle work
- Ms. Olivia rename complete
- All tests pass
- Status section updated

### After both stop:
- User runs full test suite: `uv run pytest backend/tests/ -v` + `cd frontend && npm test`
- User does end-to-end smoke test
- User reviews and commits
