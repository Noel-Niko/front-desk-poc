# BrightWheel AI Front Desk

An AI-powered front desk assistant for **Sunshine Learning Center**, a fictional childcare center. Built as a proof-of-concept for BrightWheel.

Parents can ask about center policies, hours, enrollment, illness rules — or enter a 4-digit security code to check on their child's attendance, meals, allergies, payments, and more. All answers are grounded in the CABQ Family Handbook with page-level citations.

## Prerequisites

- **Python 3.11+** and [uv](https://docs.astral.sh/uv/getting-started/installation/)
- **Node.js 18+** and npm
- **Anthropic API key** (Claude Sonnet)
- Optional: Deepgram API key (voice input), Cartesia API key (voice output)

## Setup (Clone to Running)

### 1. Clone the repository

```bash
git clone <repo-url>
cd front-desk-poc
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```
ANTHROPIC_API_KEY=sk-ant-...
DEEPGRAM_API_KEY=...          # optional — voice input
CARTESIA_API_KEY=...          # optional — voice output (Tier 2)
```

### 3. Install Python dependencies

```bash
uv sync --extra dev
```

### 4. Download handbook and build search index

```bash
make setup
```

This downloads the CABQ Family Handbook PDF, builds the FAISS + BM25 hybrid search index (101 chunks), and seeds the SQLite database with 8 demo children.

### 5. Install frontend dependencies

```bash
cd frontend && npm install --legacy-peer-deps && cd ..
```

### 6. Run the application

Open **two terminal tabs**:

**Terminal 1 — Backend (port 8000):**
```bash
make backend
```

**Terminal 2 — Frontend (port 5173):**
```bash
make frontend
```

Then open **http://localhost:5173** in your browser.

### 7. (Optional) Operator Dashboard

In a third terminal:
```bash
make dashboard
```

Open **http://localhost:8001** for the operator control center.

## Demo Guide

See [`docs/demo_questions.md`](docs/demo_questions.md) for a curated list of questions to try, including all security codes.

**Quick start conversation:**

1. Ask: *"What are your hours of operation?"* — tests handbook RAG
2. Ask: *"What's your illness policy?"* — tests multi-page citation
3. Enter security code **`7291`** (Sofia Martinez) via the PIN modal
4. Ask: *"What did Sofia eat today?"* — tests child-specific data
5. Ask: *"Does Sofia have any allergies?"* — tests allergy lookup
6. Ask: *"I need to speak to someone about billing"* — tests transfer to human

## Architecture

```
React Frontend (:5173) → Vite proxy → FastAPI Backend (:8000)
                                         ├── Claude Sonnet (tool_use)
                                         ├── FAISS + BM25 (handbook RAG)
                                         └── SQLite (child data)

Operator Dashboard (:8001) → same SQLite database
```

- **Single LLM call** with tool_use per query (no sub-agents)
- **Hybrid search**: FAISS semantic + BM25 keyword with reciprocal rank fusion
- **Date offset system**: demo data stays fresh regardless of when you run the app
- **Dependency injection**: FastAPI `app.state` + `Depends()` (no globals)

## Running Tests

```bash
# Backend (Python)
make test

# Frontend (TypeScript)
cd frontend && npm test
```

## Project Structure

```
front-desk-poc/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory + lifespan
│   │   ├── config.py            # Pydantic Settings (.env)
│   │   ├── api/
│   │   │   ├── routes.py        # REST: /chat, /verify-code, /handbook, /tour-request
│   │   │   ├── websocket.py     # WS: /voice (Deepgram relay)
│   │   │   └── dependencies.py  # DI: get_db, get_llm_service
│   │   ├── services/
│   │   │   ├── llm.py           # Claude Sonnet + tool dispatch
│   │   │   ├── handbook.py      # FAISS + BM25 hybrid RAG
│   │   │   ├── child_info.py    # DB queries + date resolution
│   │   │   └── date_utils.py    # Day offset system
│   │   ├── db/
│   │   │   ├── schema.sql       # 11 tables
│   │   │   ├── database.py      # Async SQLite wrapper
│   │   │   └── seed.py          # 8 children, 3 classrooms
│   │   └── dashboard/           # Operator dashboard (port 8001)
│   ├── data/                    # handbook.pdf, FAISS index, SQLite DB
│   └── tests/                   # pytest: 50 tests
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main layout (chat + references)
│   │   ├── components/          # Header, ChatMessage, ChatInput, PinModal, ReferencePanel
│   │   ├── hooks/useChat.ts     # Chat state management
│   │   ├── services/api.ts      # Backend API client
│   │   └── types/api.ts         # TypeScript interfaces
│   └── package.json
├── docs/
│   ├── implementation_plan.md   # Full plan with progress tracking
│   └── demo_questions.md        # Curated demo questions + security codes
├── Makefile                     # setup, backend, frontend, dashboard, test
└── .env.example
```
