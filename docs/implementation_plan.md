# BrightWheel AI Front Desk — Implementation Plan

## Status Tracker

### Tier 1: Submission-Ready (3-6 hours)

| Phase | Status |
|-------|--------|
| Phase 1: Project Setup + Backend Core | **IN PROGRESS** |
| Phase 2: React Frontend + Voice | PENDING |
| Phase 3: Operator Dashboard | PENDING |
| Phase 4: Integration + Demo Prep | PENDING |

### Tier 2: Full Implementation (extends Tier 1)

| Phase | Status |
|-------|--------|
| Phase 5: Owl Character + UI Polish | PENDING |
| Phase 6: Session Continuity + Ratings | PENDING |
| Phase 7: Advanced Operator Features | PENDING |
| Phase 8: Audio Pipeline + Fine-tuning | PENDING |
| Phase 9: TTS Voice Output | PENDING |
| Phase 10: Online Deployment | PENDING |

---

## 1. What We're Building

An **AI Front Desk** for a fictional childcare center ("Sunshine Learning Center") powered by BrightWheel. Two user-facing experiences, both run locally:

### Parent Experience (Front Desk)

- Voice-first conversational interface (text fallback always available)
- Transcription shown in real-time so parents can verify accuracy
- **Two tracks**:
  - **General info** (open to anyone): hours, policies, enrollment, illness rules, meals, field trips, tours — all grounded in the CABQ Family Handbook
  - **Child-specific info** (requires 4-digit security code): attendance, meals eaten, allergies, balance/payments, emergency contacts, field trip status
- Handbook citations displayed as clickable hyperlinks to specific PDF pages
- Child data shows **who entered it and when** (e.g., "Mrs. Elena Rodriguez, Lead Pre-K Teacher, Rm 103, 7:45 AM")
- Graceful escalation to a human when the AI doesn't know something
- Tour scheduling: collects parent info and preferred date
- **Tier 2**: Owl character ("Ollie"), session continuity, satisfaction ratings, TTS audio output

### Operator Experience (Control Center)

- **Separate application** on its own port (modeled after demo-voice-assistant-v2)
- Dashboard showing what questions are asked and where the system struggled
- Session transcripts for review
- Transfer-to-human event log with reasons
- FAQ override management (add/edit custom answers)
- **Tier 2**: Satisfaction rating aggregates, topic analytics, citation frequency

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     React Frontend (Vite + TypeScript) :5173                  │
│                                                                              │
│  ┌──────────────┐  ┌───────────────────┐  ┌────────────────────────────┐    │
│  │  Owl Avatar   │  │  Chat / Voice     │  │  Reference Panel           │    │
│  │  "Ollie"      │  │  Transcription    │  │  - Handbook page links     │    │
│  │  (static T1,  │  │  + Response text  │  │  - Child data + who/when  │    │
│  │   Lottie T2)  │  │                   │  │  - Tour request status    │    │
│  └──────────────┘  └───────────────────┘  └────────────────────────────┘    │
│         │                    │                          │                     │
│         │         ┌──────────┴──────────┐               │                     │
│         │         │  Voice: Deepgram WS  │               │                     │
│         │         │  Text: REST API      │               │                     │
│         └─────────┴─────────────────────┴───────────────┘                     │
│                              │                                                │
│                    WebSocket / REST (localhost)                               │
└──────────────────────────────┼────────────────────────────────────────────────┘
                               │
┌──────────────────────────────┼────────────────────────────────────────────────┐
│                     FastAPI Backend (Python) :8000                             │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │              Claude Sonnet — single call with tool_use                   │  │
│  │                                                                          │  │
│  │  Tools (Python functions, invoked via tool_use):                         │  │
│  │  ┌───────────────┐ ┌───────────────┐ ┌──────────────┐ ┌─────────────┐  │  │
│  │  │search_handbook │ │query_child    │ │request_tour  │ │transfer_to  │  │  │
│  │  │               │ │_info          │ │              │ │_human       │  │  │
│  │  │ FAISS+BM25    │ │ SQLite query  │ │ Insert into  │ │ Log event,  │  │  │
│  │  │ hybrid search │ │ + date logic  │ │ tour_requests│ │ provide     │  │  │
│  │  │ → chunks w/   │ │ + attribution │ │ table        │ │ contact #   │  │  │
│  │  │   page nums   │ │               │ │              │ │             │  │  │
│  │  └───────┬───────┘ └───────┬───────┘ └──────┬───────┘ └─────────────┘  │  │
│  └──────────┼─────────────────┼────────────────┼──────────────────────────┘  │
│             │                 │                 │                              │
│  ┌──────────┴──────┐  ┌──────┴─────────────────┴──────────────────────────┐  │
│  │ FAISS + BM25    │  │ SQLite Database                                    │  │
│  │ Index            │  │ children, attendance, meals, allergies,            │  │
│  │ (Handbook PDF    │  │ emergency_contacts, payments, field_trips,        │  │
│  │  bundled in      │  │ tour_requests, sessions, messages,               │  │
│  │  data/)          │  │ operator_faq_overrides                           │  │
│  │                  │  │                                                   │  │
│  │ sentence-        │  │ Date offset system: day_offset → real date       │  │
│  │ transformers     │  │ at query time. Future-awareness for today.       │  │
│  └──────────────────┘  └──────────────────────────────────────────────────┘  │
│                                                                               │
│  Endpoints:                                                                   │
│  POST /api/chat           — text chat with citations                          │
│  WS   /api/voice          — Deepgram voice pipeline                           │
│  POST /api/verify-code    — security code verification                        │
│  GET  /api/handbook/{pg}  — serve handbook PDF page (for citations)           │
│  POST /api/tour-request   — direct tour request submission                    │
│  POST /api/sessions/{id}/rate — submit session rating (Tier 2)               │
└───────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────────┐
│       Operator Dashboard (backend/app/dashboard/ — separate FastAPI) :8001     │
│       Self-contained HTML/CSS/JS in template.py (no React, no build step)     │
│       Reads from same SQLite database file                                    │
│                                                                               │
│  Endpoints:                                                                   │
│  GET  /                        — dashboard HTML                               │
│  GET  /api/sessions            — list sessions with filters                   │
│  GET  /api/sessions/{id}       — session detail + messages                    │
│  GET  /api/stats               — KPI data                                     │
│  GET  /api/struggles           — where system struggled                       │
│  GET  /api/topics              — question topic frequency                     │
│  GET  /api/faq-overrides       — list FAQ overrides                           │
│  POST /api/faq-overrides       — create override                              │
│  PUT  /api/faq-overrides/{id}  — update override                              │
│  DELETE /api/faq-overrides/{id} — delete override                             │
│  GET  /api/tour-requests       — pending tour requests                        │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Frontend** | React + Vite + TypeScript | Fast dev server, component reuse between tiers |
| **Styling** | Tailwind CSS | Rapid styling with custom BrightWheel color tokens |
| **Voice Input** | Deepgram Nova-3 via WebSocket | Sub-300ms transcription. Fallback: browser `SpeechRecognition` API |
| **Voice Output** | Tier 2: Cartesia Sonic (Lucy British) | Not in Tier 1 — text responses only |
| **Owl Character** | Tier 1: static SVG. Tier 2: Lottie animation | Static first, animated later |
| **Backend** | FastAPI (Python 3.11+) | Async, WebSocket support, type-safe, OpenAPI docs |
| **LLM** | Claude Sonnet (single call with `tool_use`) | One LLM round-trip per query. Tools are plain Python functions |
| **Anthropic SDK** | `anthropic` Python package | Official SDK for Claude API |
| **Embeddings** | sentence-transformers (`all-MiniLM-L6-v2`) | Fully local, no external API dependency. ~90MB model |
| **Vector Store** | FAISS (`faiss-cpu`) | Local, in-process, fast similarity search |
| **Keyword Search** | `rank-bm25` | Lightweight BM25 for hybrid search alongside semantic |
| **PDF Parsing** | `pymupdf` (fitz) | Extracts text with page numbers preserved |
| **Database** | SQLite + `aiosqlite` | Self-contained file, no server, async access |
| **Package Manager** | `uv` | Per project requirements |
| **Deployment** | Local only (Tier 1). Render/Vercel (Tier 2) | README-driven local setup |

**Note on `sentence-transformers`**: Pulls in PyTorch (~500MB download). If install size is a concern, `fastembed` (ONNX-based, ~50MB) is a lighter alternative with comparable quality.

### Documentation References

**Anthropic (Claude tool_use):**
- Tool Use Guide: https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview
- Tool Use Best Practices: https://docs.anthropic.com/en/docs/build-with-claude/tool-use/best-practices
- Python SDK: https://docs.anthropic.com/en/api/client-sdks
- Messages API: https://docs.anthropic.com/en/api/messages
- Streaming: https://docs.anthropic.com/en/api/streaming

**Deepgram (Voice Input / STT):**
- Python SDK Quickstart: https://developers.deepgram.com/docs/python-sdk
- Streaming (WebSocket) Guide: https://developers.deepgram.com/docs/getting-started-with-live-streaming-audio
- WebSocket API Reference: https://developers.deepgram.com/reference/streaming
- Nova-3 Model: https://developers.deepgram.com/docs/models#nova-3
- Smart Formatting: https://developers.deepgram.com/docs/smart-format
- Endpointing: https://developers.deepgram.com/docs/endpointing

**Cartesia (Voice Output / TTS):**
- Overview: https://docs.cartesia.ai/get-started/overview
- **Realtime TTS Quickstart**: https://docs.cartesia.ai/get-started/realtime-text-to-speech-quickstart
- WebSocket API: https://docs.cartesia.ai/api-reference/tts/websocket
- Compare TTS Endpoints: https://docs.cartesia.ai/api-reference/tts/compare-tts-endpoints
- Stream Inputs with Continuations: https://docs.cartesia.ai/build-with-cartesia/capability-guides/stream-inputs-with-continuations
- Sonic 3 Prompting Tips: https://docs.cartesia.ai/build-with-cartesia/sonic-3/prompting-tips
- Volume, Speed & Emotion: https://docs.cartesia.ai/build-with-cartesia/sonic-3/volume-speed-emotion

**FAISS (Vector Store):**
- Getting Started: https://github.com/facebookresearch/faiss/wiki/Getting-started
- faiss-cpu PyPI: https://pypi.org/project/faiss-cpu/

**sentence-transformers (Embeddings):**
- Quickstart: https://www.sbert.net/docs/quickstart.html
- all-MiniLM-L6-v2 Model Card: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

**fastembed (Lighter Embedding Alternative):**
- GitHub: https://github.com/qdrant/fastembed
- PyPI: https://pypi.org/project/fastembed/

**rank-bm25 (Keyword Search):**
- GitHub / PyPI: https://pypi.org/project/rank-bm25/

**pymupdf (PDF Parsing):**
- Docs: https://pymupdf.readthedocs.io/en/latest/
- Text Extraction: https://pymupdf.readthedocs.io/en/latest/recipes-text.html

**FastAPI:**
- WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
- Dependency Injection: https://fastapi.tiangolo.com/tutorial/dependencies/
- Lifespan Events: https://fastapi.tiangolo.com/advanced/events/

**React + Vite + TypeScript:**
- Vite Getting Started: https://vite.dev/guide/
- Tailwind CSS with Vite: https://tailwindcss.com/docs/guides/vite

---

## 4. BrightWheel Brand Colors

Extracted from mybrightwheel.com CSS variables:

| Token | Hex | Usage |
|-------|-----|-------|
| `blackout` | `#1E2549` | Dark navy — headers, text |
| `blueberry` | `#37458A` | Dark blue — secondary |
| `blurple` | `#5463D6` | **Primary brand** — buttons, links |
| `barney` | `#6476FF` | Lighter blue — hover states |
| `butterfly` | `#B1BAFF` | Light lavender — accents |
| `barnacle` | `#EEF1FF` | Very light — card backgrounds |
| `bubble` | `#F7F9FF` | Near white — page background |
| `sangria` | `#A40C31` | Deep red — warnings/errors |
| White | `#FFFFFF` | Cards, inputs |

Logo wheel accent colors: green `#4CAF50`, teal `#26C6DA`, purple `#7C4DFF`, pink `#FF4081`, orange `#FF9800`, red `#F44336`.

**Typography**: System fonts (clean, fast loading). Headers in `blackout`, body in a neutral dark gray.

---

## 5. Data Design

### 5.1 Handbook Knowledge Base

**Source**: CABQ Family Handbook PDF (56 pages), bundled at `data/handbook.pdf`.

**Download**: Phase 1 includes a setup script that downloads the PDF from the public CABQ URL and stores it locally. The PDF is also served by the backend at `GET /api/handbook/{page}` so the frontend can link to specific pages.

**Processing pipeline** (runs once at startup, cached to `data/handbook_index/`):
1. Extract text from PDF using `pymupdf` (fitz) — preserves page numbers
2. Chunk into ~300-token passages with 50-token overlap
3. Each chunk gets metadata: `{ page_number, section_title, chunk_id }`
4. Embed using sentence-transformers `all-MiniLM-L6-v2`
5. Store in FAISS index + parallel BM25 index on disk
6. At query time: hybrid search using reciprocal rank fusion (0.7 × semantic + 0.3 × BM25)

**Citation format** (rendered by frontend):
> "Per the Family Handbook: [illness policy text]"
> [View in Handbook (p. 43)](/api/handbook/43)

### 5.2 Fictional Center: "Sunshine Learning Center"

Based on real CABQ centers but renamed. Uses the real handbook policies since they're public. Location set to Albuquerque, NM.

- **Phone**: (505) 555-0100
- **Hours**: 7:00 AM – 5:30 PM, Monday–Friday (per handbook)
- **Address**: 1234 Sunshine Boulevard, Albuquerque, NM 87102
- **Classrooms**: Caterpillar Room (ages 0-2), Ladybug Room (ages 2-3), Butterfly Room (ages 3-5)

### 5.3 Database Schema

All tables live in a single SQLite file at `data/frontdesk.db`.

**children**
| Column | Type | Example | Notes |
|--------|------|---------|-------|
| id | INTEGER PK | 1 | |
| first_name | TEXT | "Sofia" | |
| last_name | TEXT | "Martinez" | |
| age | INTEGER | 4 | |
| classroom | TEXT | "Butterfly Room" | |
| teacher_name | TEXT | "Mrs. Elena Rodriguez" | |
| teacher_role | TEXT | "Lead Pre-K Teacher" | |
| room_number | TEXT | "Rm 103" | |
| security_code | TEXT | "7291" | 4-digit PIN |
| enrolled_date | TEXT | "2025-09-02" | ISO date |
| doctor_name | TEXT | "Dr. Sarah Chen" | Child's pediatrician |
| doctor_phone | TEXT | "(505) 555-0200" | |

**Seed data**: 8-10 children across 3 classrooms.

**attendance**
| Column | Type | Example | Notes |
|--------|------|---------|-------|
| id | INTEGER PK | 1 | |
| child_id | INTEGER FK | 1 | → children.id |
| day_offset | INTEGER | 0 | 0=today, 1=yesterday, etc. |
| check_in_time | TEXT | "07:45" | HH:MM |
| check_out_time | TEXT | "17:15" | null = still here |
| checked_in_by | TEXT | "Mrs. Elena Rodriguez, Lead Pre-K Teacher, Rm 103" | |
| checked_out_by | TEXT | "Mr. James Park, Afternoon Aide, Rm 103" | null if still here |
| status | TEXT | "present" | "present" / "absent" / "field_trip" |

**meals**
| Column | Type | Example | Notes |
|--------|------|---------|-------|
| id | INTEGER PK | 1 | |
| child_id | INTEGER FK | 1 | → children.id |
| day_offset | INTEGER | 0 | |
| meal_type | TEXT | "breakfast" | "breakfast" / "lunch" / "snack_am" / "snack_pm" |
| scheduled_time | TEXT | "08:15" | HH:MM |
| description | TEXT | "Oatmeal with fruit, milk" | |
| recorded_by | TEXT | "Mrs. Jean Walsh, Cafeteria Mgr" | |

**allergies**
| Column | Type | Example | Notes |
|--------|------|---------|-------|
| id | INTEGER PK | 1 | |
| child_id | INTEGER FK | 1 | → children.id |
| allergy_type | TEXT | "food" | "food" / "environmental" / "medication" |
| description | TEXT | "Peanuts - severe (EpiPen required)" | |
| doctor_confirmed | INTEGER | 1 | 0/1 boolean |
| recorded_by | TEXT | "Mrs. Elena Rodriguez, Lead Pre-K Teacher, Rm 103" | |
| recorded_date | TEXT | "2025-09-02" | ISO date |

**emergency_contacts**
| Column | Type | Example | Notes |
|--------|------|---------|-------|
| id | INTEGER PK | 1 | |
| child_id | INTEGER FK | 1 | → children.id |
| contact_name | TEXT | "Maria Martinez" | |
| relationship | TEXT | "Mother" | |
| phone | TEXT | "(505) 555-0142" | |
| is_primary | INTEGER | 1 | 0/1 boolean |
| recorded_by | TEXT | "Admin Office" | |
| recorded_date | TEXT | "2025-09-02" | |

**payments**
| Column | Type | Example | Notes |
|--------|------|---------|-------|
| id | INTEGER PK | 1 | |
| child_id | INTEGER FK | 1 | → children.id |
| current_balance | REAL | 125.00 | Amount owed |
| next_payment_days_ahead | INTEGER | 4 | Days from today until due (always positive) |
| last_payment_amount | REAL | 250.00 | |
| last_payment_date_offset | INTEGER | 14 | Days ago (consistent with day_offset) |
| fee_type | TEXT | "Preschool Extended Care" | |
| weekly_fee | REAL | 65.00 | |

**field_trips** (classroom-level; per-child tracking is Tier 2)
| Column | Type | Example | Notes |
|--------|------|---------|-------|
| id | INTEGER PK | 1 | |
| day_offset | INTEGER | 2 | |
| description | TEXT | "Walking trip to Tiguex Park" | |
| departure_time | TEXT | "10:00" | HH:MM |
| return_time | TEXT | "11:30" | HH:MM |
| classrooms | TEXT | "Butterfly Room, Ladybug Room" | Comma-separated |
| recorded_by | TEXT | "Mrs. Elena Rodriguez, Lead Pre-K Teacher, Rm 103" | |

**Note**: To query "Was Sofia on the field trip?", the `query_child_info` tool matches `field_trips.classrooms` against the child's classroom via `LIKE '%Butterfly Room%'`.

**tour_requests**
| Column | Type | Example | Notes |
|--------|------|---------|-------|
| id | INTEGER PK | 1 | |
| parent_name | TEXT | "Alex Johnson" | |
| parent_phone | TEXT | "(505) 555-0333" | |
| parent_email | TEXT | "alex@example.com" | Optional |
| child_age | INTEGER | 3 | Optional |
| preferred_date | TEXT | "next Tuesday" | Free-text, as stated by parent |
| notes | TEXT | "Interested in Ladybug Room" | Optional |
| created_at | TEXT | ISO datetime | |
| status | TEXT | "pending" | "pending" / "confirmed" / "cancelled" |

**sessions**
| Column | Type | Example | Notes |
|--------|------|---------|-------|
| id | TEXT PK | uuid4 | |
| started_at | TEXT | ISO datetime | |
| ended_at | TEXT | ISO datetime | null until session ends |
| security_code_used | TEXT | "7291" | null if general track |
| child_id | INTEGER FK | 1 | null if general track |
| previous_session_id | TEXT FK | uuid | Tier 2: for continuity |
| summary | TEXT | "Asked about allergies and pickup" | Tier 2: AI-generated |
| rating | INTEGER | 4 | Tier 2: 1-5 stars |
| rating_feedback | TEXT | "Very helpful!" | Tier 2: optional text |
| transferred_to_human | INTEGER | 0 | 0/1 boolean |
| transfer_reason | TEXT | "Billing dispute" | null if no transfer |
| input_mode | TEXT | "voice" | "voice" / "text" |

**messages**
| Column | Type | Example | Notes |
|--------|------|---------|-------|
| id | INTEGER PK | auto | |
| session_id | TEXT FK | uuid | → sessions.id |
| role | TEXT | "user" | "user" / "assistant" / "system" |
| content | TEXT | message text | |
| citations | TEXT | JSON array | `[{"page": 12, "section": "Illness Policy", "text": "..."}]` |
| tool_used | TEXT | "search_handbook" | Which tool was invoked, if any |
| transcript_confidence | REAL | 0.97 | Deepgram confidence (null for text input) |
| raw_audio_path | TEXT | path | Tier 2: stored audio file |
| timestamp | TEXT | ISO datetime | |

**operator_faq_overrides**
| Column | Type | Example | Notes |
|--------|------|---------|-------|
| id | INTEGER PK | auto | |
| question_pattern | TEXT | "What are your hours?" | |
| answer | TEXT | "We're open 7 AM to 5:30 PM..." | |
| created_by | TEXT | "Admin" | |
| created_at | TEXT | ISO datetime | |
| updated_at | TEXT | ISO datetime | null until edited |
| active | INTEGER | 1 | 0/1 boolean |

### 5.4 Date Offset System

All event dates use `day_offset` (integer, 0 = today, 1 = yesterday, etc.) so demo data stays fresh regardless of when the app is run.

```python
from datetime import date, datetime, timedelta

def resolve_date(day_offset: int) -> date:
    """Convert day_offset to a real date. 0=today, 1=yesterday."""
    return date.today() - timedelta(days=day_offset)

def resolve_datetime(day_offset: int, time_str: str) -> datetime:
    """Convert day_offset + HH:MM time to a real datetime."""
    d = resolve_date(day_offset)
    t = datetime.strptime(time_str, "%H:%M").time()
    return datetime.combine(d, t)

def is_future(day_offset: int, time_str: str) -> bool:
    """Check if the resolved datetime is in the future."""
    return resolve_datetime(day_offset, time_str) > datetime.now()
```

**Critical rule for the LLM**: When `day_offset == 0` (today) and the event time is in the future, frame it as **scheduled/planned**, not past tense:
- 11:00 AM query about 12:00 PM lunch → "Sofia is scheduled to have chicken nuggets for lunch today"
- 2:00 PM query about 8:00 AM breakfast → "Sofia had oatmeal with fruit for breakfast this morning"

**Payments**: `next_payment_days_ahead` uses a forward-looking offset (positive = future). Resolved as: `date.today() + timedelta(days=next_payment_days_ahead)`.

**Weekend handling**: Seed data generator only creates records for weekday `day_offset` values (skips offsets that resolve to Saturday/Sunday). If the app is run on a weekend, `day_offset=0` will have no attendance/meal data, and the LLM should note "the center is closed on weekends."

### 5.5 Seed Data

The seed data generator (`scripts/seed_data.py`) creates:

- **8-10 children** across 3 classrooms with unique security codes
- **5 weekdays of attendance** (day_offsets 0-6, skipping weekends)
- **4 meals per child per weekday** (breakfast, AM snack, lunch, PM snack)
- **1-2 allergies** for ~half the children
- **2-3 emergency contacts** per child
- **1 payment record** per child with realistic balances
- **2-3 field trips** spread across recent days
- **A few example sessions and messages** so the operator dashboard has data on first run

Seed data is idempotent: running it again resets the database to a known state.

---

## 6. Feature Details

### 6.1 Single LLM Call with Tools

**No sub-agents. No orchestrator/router pattern.** One Claude Sonnet API call per user message, using `tool_use` to invoke Python functions as needed.

```python
# Module-level constant (acceptable per CLAUDE.md)
SYSTEM_PROMPT_TEMPLATE = """
You are Ollie, the friendly AI Front Desk assistant for Sunshine Learning Center,
a childcare center powered by BrightWheel.

Current date and time: {current_datetime}

You help parents with two types of questions:
1. GENERAL: Center policies, hours, enrollment, illness rules, meals, field trips, tours.
   Use the search_handbook tool to find answers. ALWAYS cite the page number.
2. CHILD-SPECIFIC: Attendance, meals, allergies, emergency contacts, payments, field trips
   for a specific child. Requires a verified 4-digit security code.
   Use the query_child_info tool. ALWAYS include who recorded the data and when.

CRITICAL RULES:
1. NEVER make up information. Only state facts from your tools or the handbook.
2. When citing the handbook, ALWAYS include the page number.
3. If you don't know or your tools return no results, say so and offer to transfer to staff.
4. For child-specific queries, the security code MUST be verified first.
5. Be warm, concise, and reassuring. These are busy, caring parents.
6. When reporting today's events, check the time — don't report future events as past.
7. If the parent wants to schedule a tour, use the request_tour tool to collect their info.
8. For sensitive topics (custody, abuse concerns, billing disputes), transfer to human.

{faq_overrides_context}
{session_continuity_context}
"""

# Tools registered with Claude API
TOOLS = [
    {
        "name": "search_handbook",
        "description": "Search the center's Family Handbook for policies, procedures, hours, illness rules, enrollment info, etc. Returns relevant passages with page numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_child_info",
        "description": "Query child-specific information. Only available after security code is verified. Returns attendance, meals, allergies, emergency contacts, payments, or field trips.",
        "input_schema": {
            "type": "object",
            "properties": {
                "child_id": {"type": "integer"},
                "info_type": {
                    "type": "string",
                    "enum": ["attendance", "meals", "allergies", "emergency_contacts", "payments", "field_trips", "overview"]
                },
                "day_offset": {
                    "type": "integer",
                    "description": "0=today, 1=yesterday, etc. Default 0."
                }
            },
            "required": ["child_id", "info_type"]
        }
    },
    {
        "name": "request_tour",
        "description": "Schedule a tour for a prospective parent. Collect their name, phone, and preferred date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_name": {"type": "string"},
                "parent_phone": {"type": "string"},
                "parent_email": {"type": "string"},
                "child_age": {"type": "integer"},
                "preferred_date": {"type": "string"},
                "notes": {"type": "string"}
            },
            "required": ["parent_name", "parent_phone", "preferred_date"]
        }
    },
    {
        "name": "transfer_to_human",
        "description": "Transfer the conversation to a human staff member. Use when: the question is outside your knowledge, the parent is frustrated, the topic is sensitive (custody, billing disputes, abuse), or the parent explicitly asks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why the transfer is needed"}
            },
            "required": ["reason"]
        }
    }
]
```

**Dependency injection pattern** (per CLAUDE.md — no global variables):

```python
from fastapi import Depends, Request

# Dependencies injected via app.state
def get_handbook_index(request: Request) -> HandbookIndex:
    return request.app.state.handbook_index

def get_db(request: Request) -> Database:
    return request.app.state.db

def get_anthropic_client(request: Request) -> anthropic.AsyncAnthropic:
    return request.app.state.anthropic_client

# Tool handler receives dependencies, not globals
async def handle_search_handbook(
    query: str,
    index: HandbookIndex,
) -> list[HandbookChunk]:
    semantic_results = index.semantic_search(query, top_k=5)
    bm25_results = index.keyword_search(query, top_k=5)
    return reciprocal_rank_fusion(semantic_results, bm25_results)[:5]
```

### 6.2 Handbook Search (Hybrid RAG)

```python
def reciprocal_rank_fusion(
    semantic_results: list[HandbookChunk],
    bm25_results: list[HandbookChunk],
    k: int = 60,
    semantic_weight: float = 0.7,
    bm25_weight: float = 0.3,
) -> list[HandbookChunk]:
    """Merge semantic + keyword results using reciprocal rank fusion."""
    scores: dict[str, float] = {}
    chunk_map: dict[str, HandbookChunk] = {}

    for rank, chunk in enumerate(semantic_results):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + semantic_weight / (k + rank + 1)
        chunk_map[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(bm25_results):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + bm25_weight / (k + rank + 1)
        chunk_map[chunk.chunk_id] = chunk

    sorted_ids = sorted(scores, key=scores.get, reverse=True)
    return [chunk_map[cid] for cid in sorted_ids]
```

Each result includes `page_number` for citation. The LLM receives the chunks and must include page references in its response.

### 6.3 Security Code + Child Info

Flow:
1. Parent says "I want to check on my child" (or similar)
2. LLM recognizes child-specific intent, asks for 4-digit security code
3. Frontend shows a PIN entry UI (4 digit boxes)
4. Code sent to `POST /api/verify-code` → returns `{ verified: true, child_id: 1, child_name: "Sofia Martinez" }`
5. Session is now "authenticated" — `query_child_info` tool becomes available
6. If invalid after 3 attempts: LLM uses `transfer_to_human` tool

**Security code state** is tracked per session (in-memory dict keyed by session_id). The LLM's system prompt is updated to include the verified child_id so it can use the tool.

### 6.4 Date-Aware Response Framing

The system prompt includes `current_datetime` so the LLM can reason about past vs. future:

```
Current date and time: Monday, March 17, 2026 at 2:30 PM
```

The `query_child_info` tool returns data with resolved timestamps and a `temporal_hint` field:

```python
# Tool output example for a meal query
{
    "child_name": "Sofia Martinez",
    "info_type": "meals",
    "current_time": "2:30 PM",
    "data": [
        {
            "meal_type": "breakfast",
            "time": "8:15 AM",
            "description": "Oatmeal with fruit, milk",
            "recorded_by": "Mrs. Jean Walsh, Cafeteria Mgr",
            "temporal_hint": "past"  # 8:15 AM < 2:30 PM
        },
        {
            "meal_type": "snack_pm",
            "time": "3:00 PM",
            "description": "Apple slices, cheese crackers",
            "recorded_by": "Mrs. Jean Walsh, Cafeteria Mgr",
            "temporal_hint": "future"  # 3:00 PM > 2:30 PM
        }
    ]
}
```

### 6.5 Tour Scheduling

The assignment explicitly lists "How can I schedule a tour?" as a common parent question.

Flow:
1. Parent asks about tours
2. LLM uses `request_tour` tool, conversationally collecting: name, phone, preferred date
3. Tool inserts a row into `tour_requests` with status="pending"
4. LLM confirms: "I've submitted your tour request for [date]. A staff member will call you at [phone] to confirm. Is there anything else I can help with?"
5. Operator dashboard shows pending tour requests

### 6.6 Graceful Escalation

Triggers for `transfer_to_human`:
- User explicitly asks to speak to someone
- LLM's tools return no relevant results (handbook search score below threshold)
- Sensitive topics: custody issues, abuse concerns, billing disputes
- Child info query with 3 failed security code attempts
- User frustration detected (repeated questions, negative sentiment)

Escalation response pattern: "I want to make sure you get the right answer. Let me connect you with a staff member. You can reach Sunshine Learning Center at (505) 555-0100, or I can have someone call you back. Would you like to leave a message?"

The `transfer_to_human` tool logs the event in the `sessions` table (`transferred_to_human=1`, `transfer_reason=...`).

### 6.7 Voice Input Pipeline

Adapted from **poc-deepgram** architecture:

```
Browser mic → AudioContext 16kHz → PCM16 → WebSocket → FastAPI → Deepgram WS
                                                                    ↓
Browser ← JSON events ← WebSocket ← FastAPI ← Transcript events ←──┘
```

**WebSocket protocol** (`WS /api/voice`):

Client → Server messages:
- Binary frames: raw PCM16 audio chunks
- JSON: `{"type": "config", "session_id": "..."}` (sent on connect)

Server → Client messages:
- `{"type": "transcript", "text": "...", "is_final": false}` — interim transcript
- `{"type": "transcript", "text": "...", "is_final": true, "confidence": 0.97}` — final
- `{"type": "response", "text": "...", "citations": [...]}` — LLM response
- `{"type": "error", "message": "..."}` — error

**Fallback**: If no Deepgram API key is configured, the frontend uses the browser's built-in `SpeechRecognition` API (WebkitSpeechRecognition). In this mode, transcription happens client-side and final text is sent via `POST /api/chat`.

### 6.8 Session Continuity (Tier 2)

When a parent authenticates with a security code:
1. Query `sessions` for recent entries (last 7 days) with the same `security_code_used`
2. If found, load the `summary` from the most recent session
3. Set `previous_session_id` on the new session
4. Inject into system prompt: "In your last visit on [date], you asked about [summary]. Do you have any follow-up questions about that?"

**Summary generation**: At session end, a Haiku call summarizes the conversation into 1-2 sentences for future reference.

### 6.9 Satisfaction Rating (Tier 2)

At conversation end (user says goodbye or clicks "End Chat"):
1. Show 1-5 star rating (clickable stars)
2. Optional: "Any feedback for us?" text input
3. Store `rating` and `rating_feedback` in `sessions` table

---

## 7. UI Layout

### Tier 1 Layout (two-panel + header)

```
┌──────────────────────────────────────────────────────────────────┐
│  [BW Logo] Sunshine Learning Center AI Front Desk    [🎙️ ⌨️]    │  ← Header + voice/text toggle
├────────────────────────────────────┬─────────────────────────────┤
│                                    │                             │
│     Conversation Area              │  📄 References              │
│                                    │                             │
│  ┌──────────────────────────┐      │  Handbook links:            │
│  │ 🦉 Hi! I'm Ollie, your │      │  • Illness Policy (p.43) ↗  │
│  │ AI Front Desk assistant. │      │  • Hours of Op (p.31) ↗     │
│  │ How can I help you today?│      │                             │
│  └──────────────────────────┘      │  Child info:                │
│                                    │  • "Checked in at 7:45 AM   │
│  ┌──────────────────────────┐      │    by Mrs. Rodriguez"       │
│  │ You: What time does the  │      │    (today, 7:45 AM)         │
│  │ center open?             │      │                             │
│  └──────────────────────────┘      │  Tour requests:             │
│                                    │  • "Tour requested for      │
│  ┌──────────────────────────┐      │    next Tuesday"            │
│  │ 🦉 The center opens at  │      │                             │
│  │ 7:00 AM (Handbook p.31). │      │                             │
│  └──────────────────────────┘      │                             │
│                                    │                             │
├────────────────────────────────────┴─────────────────────────────┤
│  🎙️ [  Listening... "what time does..."  ] [Send]               │
│  [🔴 Recording]                    [Type instead]                │
└──────────────────────────────────────────────────────────────────┘
```

### Tier 2 Layout (three-panel with animated owl)

Adds a left panel with an animated Lottie owl character:
- **Idle**: slow blink + gentle sway
- **Listening**: ear tilt, eyes wide, subtle lean forward
- **Speaking**: head bobs, wings move slightly

On mobile: owl collapses to a small avatar above the chat. References panel becomes a slide-out drawer.

---

## 8. Tier 1: Submission Plan (3-6 hours)

Everything in Tier 1 produces a complete, demo-ready submission. Code is structured so Tier 2 features plug in without refactoring.

### Phase 1: Project Setup + Backend Core

Architecture follows the `demo-voice-assistant-v2` patterns: lifespan context manager, `app.state` DI, `api/dependencies.py`, dashboard as a sub-package, Makefile for automation.

- [ ] Initialize project structure:
  ```
  front-desk-poc/
  ├── backend/
  │   ├── app/
  │   │   ├── __init__.py
  │   │   ├── main.py              # FastAPI app factory + lifespan manager
  │   │   ├── config.py            # Pydantic Settings (reads .env)
  │   │   ├── api/
  │   │   │   ├── routes.py        # REST endpoints (chat, verify, tour, handbook)
  │   │   │   ├── websocket.py     # WS /api/voice endpoint
  │   │   │   └── dependencies.py  # DI functions (get_db, get_handbook_index, etc.)
  │   │   ├── models/
  │   │   │   ├── schemas.py       # Pydantic request/response models
  │   │   │   └── database.py      # aiosqlite engine + session helpers
  │   │   ├── services/
  │   │   │   ├── llm.py           # Claude Sonnet + tool dispatch
  │   │   │   ├── handbook.py      # RAG: FAISS + BM25 hybrid search
  │   │   │   ├── child_info.py    # DB queries + date resolution
  │   │   │   ├── session.py       # Session management
  │   │   │   └── tools.py         # Tool handler implementations
  │   │   ├── db/
  │   │   │   ├── database.py      # aiosqlite wrapper
  │   │   │   ├── schema.sql       # CREATE TABLE statements
  │   │   │   └── seed.py          # Seed data generator
  │   │   └── dashboard/           # Operator dashboard (separate FastAPI app)
  │   │       ├── server.py        # FastAPI app on :8001
  │   │       ├── service.py       # Analytics queries + data processing
  │   │       ├── schemas.py       # Dashboard data models
  │   │       └── template.py      # Embedded HTML/CSS/JS template
  │   ├── data/
  │   │   ├── handbook.pdf         # Downloaded CABQ handbook
  │   │   └── handbook_index/      # FAISS + BM25 cached index
  │   ├── scripts/
  │   │   ├── download_handbook.py # Fetch PDF from CABQ URL
  │   │   └── build_index.py       # Process PDF → FAISS + BM25
  │   ├── tests/
  │   │   ├── test_rag.py          # Handbook search accuracy
  │   │   ├── test_date_offset.py  # Date resolution + future-awareness
  │   │   ├── test_child_info.py   # Child data queries
  │   │   └── test_chat.py         # Chat endpoint integration
  │   └── pyproject.toml
  ├── frontend/                    # React + Vite + TypeScript (Phase 2)
  ├── Makefile                     # Build/run automation
  ├── .env.example
  └── README.md
  ```
- [ ] Update `pyproject.toml` with all dependencies (see Section 10)
- [ ] Create `config.py` with `pydantic-settings` (reads `.env`)
- [ ] Create `.env.example` (see Section 10)
- [ ] Create `Makefile` with targets: `setup`, `backend`, `frontend`, `dashboard`, `seed`, `test`, `dev` (runs all three)
- [ ] Download CABQ handbook PDF → `data/handbook.pdf`
- [ ] PDF processing: extract text, chunk, embed, build FAISS + BM25 index
- [ ] Hybrid search function with reciprocal rank fusion
- [ ] SQLite schema creation + seed data generator
- [ ] Date offset resolution functions with future-awareness
- [ ] FastAPI app with lifespan context manager (startup: init DB, load index, create Anthropic client → `app.state`)
- [ ] `api/dependencies.py` — DI functions: `get_db()`, `get_handbook_index()`, `get_anthropic_client()`
- [ ] `POST /api/chat` — text chat endpoint with Claude Sonnet + tool_use
- [ ] Tool implementations: `search_handbook`, `query_child_info`, `request_tour`, `transfer_to_human`
- [ ] `POST /api/verify-code` — security code verification
- [ ] `GET /api/handbook/{page}` — serve handbook PDF page
- [ ] `WS /api/voice` — Deepgram WebSocket relay (audio in → transcript + LLM response out)
- [ ] Session creation + message logging to SQLite
- [ ] FAQ override lookup (operator can add these via dashboard)
- [ ] Tests: RAG accuracy, date resolution, child info queries

### Phase 2: React Frontend + Voice

- [ ] Initialize React + Vite + TypeScript project in `frontend/`
- [ ] Install Tailwind CSS, configure BrightWheel color tokens
- [ ] Two-panel layout: conversation area | reference panel
- [ ] Header: BrightWheel logo + center name + voice/text toggle
- [ ] Chat bubble components (user messages + assistant messages)
- [ ] Citation rendering in assistant messages (linked page numbers)
- [ ] Reference panel: handbook citations list + child data attribution cards
- [ ] Text input bar with send button
- [ ] Deepgram WebSocket integration for voice input:
  - Mic permission request + audio capture
  - WebSocket connection to `WS /api/voice`
  - Interim transcript display (gray text, updating)
  - Final transcript display (black text, sent to LLM)
- [ ] Fallback: browser `SpeechRecognition` API if no Deepgram key
- [ ] Security code entry modal (4-digit PIN input)
- [ ] Static owl SVG/emoji as avatar in chat bubbles (Lottie animation is Tier 2)
- [ ] Loading states (typing indicator while LLM responds)
- [ ] Error states (connection lost, API error)
- [ ] Tour request confirmation display in reference panel

### Phase 3: Operator Dashboard

Following the `demo-voice-assistant-v2` dashboard pattern: separate FastAPI app in `backend/app/dashboard/`, self-contained HTML in `template.py`, runs on its own port via `make dashboard`.

- [ ] Create `backend/app/dashboard/` package:
  - `server.py` — FastAPI app on `:8001`
  - `service.py` — Analytics queries (session stats, struggle detection, topic frequency)
  - `schemas.py` — Pydantic response models for dashboard data
  - `template.py` — Embedded HTML/CSS/JS dashboard (BrightWheel-themed, no build step)
- [ ] Main dashboard page with:
  - Session log table (timestamp, duration, topic, transferred?, input mode)
  - "Where system struggled" section (sessions with transfers or tool failures)
  - Question topic frequency (based on `tool_used` column in messages)
  - Pending tour requests list
- [ ] Session detail view: click a session → see full message transcript
- [ ] FAQ override management:
  - List existing overrides
  - Add new override (question pattern + answer)
  - Edit/deactivate existing override
- [ ] Auto-refresh (poll every 30 seconds)
- [ ] Reads from same `data/frontdesk.db` file (SQLite WAL mode for concurrent reads)
- [ ] Add `make dashboard` target to Makefile

### Phase 4: Integration + Demo Prep

- [ ] README with complete local setup instructions:
  - Prerequisites: Python 3.11+, Node.js 18+, uv
  - Environment setup: copy `.env.example` → `.env`, add API keys
  - Quick start: `make setup && make dev` (runs backend + frontend + dashboard)
  - Individual: `make backend`, `make frontend`, `make dashboard`
  - Manual: `cd backend && uv run python -m scripts.download_handbook && uv run python -m scripts.build_index && uv run uvicorn app.main:create_app --factory --port 8000`
- [ ] End-to-end smoke test: text chat, voice chat, security code flow, tour request, escalation
- [ ] Verify operator dashboard shows session data
- [ ] Record < 2 min demo video (or write < 1 page explanation doc)
- [ ] Final cleanup: remove debug prints, check error messages

---

## 9. Tier 2: Full Implementation

Each phase extends Tier 1 code without refactoring. The schema already has columns for Tier 2 features (they're just null/unused in Tier 1).

### Phase 5: Owl Character + UI Polish

- [ ] Find/create Lottie owl animation with idle/speaking/listening states
- [ ] Upgrade to three-panel layout: owl | chat | references
- [ ] Implement state transitions: idle ↔ listening ↔ speaking
- [ ] "That's not what I said" button — allows editing final transcript before sending
- [ ] Mobile responsive: owl collapses to avatar, references become slide-out drawer
- [ ] Smooth scroll to latest message
- [ ] Keyboard shortcuts (Enter to send, Escape to cancel recording)

### Phase 6: Session Continuity + Ratings

- [ ] Session summary generation via Claude Haiku at conversation end
- [ ] Previous session lookup by security code (last 7 days)
- [ ] Populate `previous_session_id` on session creation
- [ ] Inject continuity context into system prompt
- [ ] End-of-conversation flow: goodbye detection → rating prompt
- [ ] Star rating UI (1-5 clickable stars)
- [ ] Optional feedback text input
- [ ] Store rating + feedback in `sessions` table

### Phase 7: Advanced Operator Features

- [ ] KPI cards with charts: total sessions, avg rating, transfer rate trend
- [ ] Rating distribution histogram
- [ ] Topic breakdown pie/bar chart
- [ ] Citation frequency: which handbook sections are cited most
- [ ] "Answers that led to low ratings" — flag for review
- [ ] Session filtering: by date range, by rating, by transfer status
- [ ] Export session data as CSV

### Phase 8: Audio Pipeline + Fine-tuning

- [ ] Raw audio chunk storage: WebSocket → `data/audio/{session_id}/{message_id}.webm`
- [ ] Link audio files in `messages.raw_audio_path`
- [ ] Export script: generate paired audio+transcript dataset
- [ ] Data format compatible with common fine-tuning frameworks

### Phase 9: TTS Voice Output (Cartesia Sonic)

**Cartesia Docs Reference:**
- Overview: https://docs.cartesia.ai/get-started/overview
- **Realtime TTS Quickstart**: https://docs.cartesia.ai/get-started/realtime-text-to-speech-quickstart
- Make an API Request: https://docs.cartesia.ai/get-started/make-an-api-request
- WebSocket API: https://docs.cartesia.ai/api-reference/tts/websocket
- Compare TTS Endpoints (WS vs REST vs SSE): https://docs.cartesia.ai/api-reference/tts/compare-tts-endpoints
- Working with WebSockets: https://docs.cartesia.ai/api-reference/tts/working-with-web-sockets/contexts
- Context Flushing & Flush IDs: https://docs.cartesia.ai/api-reference/tts/working-with-web-sockets/context-flushing-and-flush-i-ds
- Stream Inputs with Continuations: https://docs.cartesia.ai/build-with-cartesia/capability-guides/stream-inputs-with-continuations
- TTS Models (Sonic 3 latest): https://docs.cartesia.ai/build-with-cartesia/tts-models/latest
- Sonic 3 Prompting Tips: https://docs.cartesia.ai/build-with-cartesia/sonic-3/prompting-tips
- Sonic 3 SSML Tags: https://docs.cartesia.ai/build-with-cartesia/sonic-3/ssml-tags
- Volume, Speed & Emotion Control: https://docs.cartesia.ai/build-with-cartesia/sonic-3/volume-speed-emotion
- Choosing TTS Parameters: https://docs.cartesia.ai/build-with-cartesia/capability-guides/choosing-tts-parameters
- Choosing a Voice: https://docs.cartesia.ai/build-with-cartesia/capability-guides/choosing-a-voice
- Voice IDs: https://docs.cartesia.ai/build-with-cartesia/tts-models/voice-ids
- REST Bytes Endpoint: https://docs.cartesia.ai/api-reference/tts/bytes
- REST SSE Endpoint: https://docs.cartesia.ai/api-reference/tts/sse

**Tasks:**
- [ ] Cartesia Sonic WebSocket integration for text-to-speech (voice: Lucy British, ID 2f251ac3-89a9-4a77-a452-704b474ccd01)
- [ ] Toggle: text only / audio only / both
- [ ] Sync owl animation with TTS playback (Tier 2 owl required)
- [ ] Sentence-level progressive synthesis (pipeline: split → synthesize first sentence → stream to client while synthesizing next)

### Phase 10: Online Deployment

- [ ] CORS middleware configuration for cross-origin requests
- [ ] Deploy backend to Render (or Railway/Fly.io)
- [ ] Deploy frontend to Vercel
- [ ] Deploy operator dashboard to Render (second service)
- [ ] Environment variables configured per platform
- [ ] Health check endpoints for monitoring
- [ ] Loading states for cold starts

---

## 10. Environment Variables

**`.env.example`**:
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Required for voice input (optional — falls back to browser SpeechRecognition)
DEEPGRAM_API_KEY=

# Required for voice output (TTS)
CARTESIA_API_KEY=
CARTESIA_VOICE_ID=2f251ac3-89a9-4a77-a452-704b474ccd01  # Lucy British

# Optional
DATABASE_PATH=./data/frontdesk.db
HANDBOOK_PDF_PATH=./data/handbook.pdf
HANDBOOK_INDEX_PATH=./data/handbook_index/
LOG_LEVEL=INFO
CLAUDE_MODEL=claude-sonnet-4-20250514
```

---

## 11. Open Questions

### MUST RESOLVE BEFORE CODING

1. **Google Doc access**: The BrightWheel market primer at `https://docs.google.com/document/d/1aLMQ77r2rQNsQdZ-U9VXpje1pWKZYJxtyJwCJ3H1TPc/` requires Google sign-in. Options:
   - Make it publicly accessible (Share → Anyone with the link)?
   - Copy-paste the contents into `docs/brightwheel_market_primer.txt`?
   - Proceed without it (the assignment doc + public BrightWheel info is sufficient)?

2. **Deepgram API key**: Do you have one? If not, Tier 1 will use browser `SpeechRecognition` API as the voice input method (less accurate but free, no key needed).

3. **Anthropic API key**: Confirm you have access to Claude Sonnet. Haiku is needed only in Tier 2 (session summaries).

4. **Owl asset**: For Tier 1, we'll use a static SVG/emoji owl. For Tier 2, options:
   - LottieFiles free owl animation
   - CSS-animated SVG (no licensing concerns)
   - AI-generated custom owl character

5. **Audio output (TTS)**: Tier 2 only. **RESOLVED** — Cartesia Sonic, voice "Lucy British" (ID: `2f251ac3-89a9-4a77-a452-704b474ccd01`). ~100ms latency, WebSocket streaming, highest speed available.

---

## 12. Key Differentiators (Why This Wins)

1. **Voice-first with real-time transcription** — Most candidates will build a text chatbot. Voice shows product vision.
2. **Handbook citations with page links** — Trustworthiness through transparency. Parents can verify.
3. **Child-specific data track with attribution** — Shows depth of thinking about what parents actually need. Every data point attributed to who recorded it and when.
4. **Date-aware intelligence** — Dynamic data that feels real, not static demo data. Future events framed as scheduled, past events framed as completed.
5. **Tour scheduling** — Directly addresses an assignment example. Shows the system can *do things*, not just answer questions.
6. **Graceful escalation** — Mature AI product thinking (knowing when NOT to answer).
7. **Operator dashboard** — Complete story: parent experience + staff experience + improvement loop. Separate app shows production architecture thinking.
8. **FAQ overrides** — Operators can improve the system without touching code. Flywheel effect.
9. **BrightWheel brand alignment** — Colors, typography, and tone match the real product.
10. **Clean architecture** — Single LLM call with tools (fast), DI patterns (testable), 2-tier plan (shippable + extensible).

---

## 13. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Handbook RAG returns wrong info | Hybrid search + confidence threshold + "I'm not sure" fallback + escalation |
| Deepgram API issues | Browser `SpeechRecognition` as automatic fallback (no key needed) |
| LLM hallucinates child data | Tool-use pattern ensures LLM can only return what the DB contains |
| sentence-transformers install too slow | Alternative: `fastembed` (ONNX, ~50MB vs ~500MB) |
| Owl animation performance | Tier 1 uses static SVG. Lottie is GPU-accelerated for Tier 2 |
| Weekend demo | Seed data includes weekday-only records; system acknowledges "center is closed on weekends" |
| Security code brute force | 3-attempt limit per session, then forced escalation to human |
| SQLite concurrent access (backend + operator) | SQLite WAL mode allows concurrent reads. Operator dashboard is read-heavy |
