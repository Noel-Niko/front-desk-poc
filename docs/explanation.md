# BrightWheel AI Front Desk — Explanation

## What I Built

An AI-powered front desk assistant for a fictional childcare center ("Sunshine Learning Center") with two user experiences:

**Parent Interface** (React, port 5173): A chat-based assistant that handles general center questions (hours, illness policy, enrollment, tours) using RAG over the 56-page CABQ Family Handbook, and child-specific queries (attendance, meals, allergies, payments) after 4-digit security code verification. Every answer cites specific handbook pages or shows who recorded the data and when.

**Operator Dashboard** (embedded HTML, port 8001): A control center showing session logs, system struggles, FAQ override management, and pending tour requests — all reading from the same SQLite database.

## Key Technical Decisions

- **Single Claude Sonnet call with tool_use** — no sub-agents or orchestrator. One LLM round-trip per query with four tools (search_handbook, query_child_info, request_tour, transfer_to_human). This keeps latency low and the architecture simple.
- **Hybrid RAG (FAISS + BM25)** — semantic embeddings for conceptual questions, keyword search for exact terms like "immunization" or "EpiPen". Reciprocal rank fusion (70% semantic, 30% keyword) produces the best results across 101 handbook chunks.
- **Date offset system** — all demo data uses relative offsets (0=today, 1=yesterday) so the app produces fresh, realistic data every time it runs. No stale dates.
- **Dependency injection via FastAPI app.state** — no global variables. All singletons (DB, LLM service, handbook index) are created at startup and injected via `Depends()`.

## Architecture

```
React (:5173) → Vite proxy → FastAPI (:8000) → Claude Sonnet (tool_use)
                                                ├── FAISS + BM25 (handbook)
                                                └── SQLite (child data)
Dashboard (:8001) → same SQLite (WAL mode)
```

## What I'd Do Next

1. **Voice input** (Deepgram WebSocket) — the hook is built, needs the audio pipeline
2. **TTS output** (Cartesia Sonic) — for a fully voice-first experience
3. **Session continuity** — remember returning parents across visits
4. **Animated owl character** — Lottie animation for Ollie with listening/speaking states

## Test Coverage

- Backend: 61 tests (pytest) — RAG search quality, date offset logic, child info queries, API integration, dashboard endpoints
- Frontend: 29 tests (Vitest) — component rendering, user interactions, voice hook
