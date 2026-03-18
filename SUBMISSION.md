# AI Front Desk — Submission

**To:** Waqas Ahmed, CTO at brightwheel
**From:** Noel Nosse

---

## What It Is

A voice-and-text AI front desk for childcare centers. Parents ask questions via chat or speech; the system answers from a real 56-page handbook (CABQ Family Handbook) using hybrid RAG. Child-specific queries (attendance, meals, allergies) require PIN authentication. Operators get a dashboard showing session logs, system struggles, FAQ overrides, and tour requests.

**Stack:** React + FastAPI + Claude Sonnet (single `tool_use` call per query) + FAISS/BM25 hybrid search + Deepgram STT + Cartesia TTS + SQLite

## Video Demos

| Interaction | Link                                                 |
|---|------------------------------------------------------|
| Text — General questions | [youtu.be/_fap9GElVeI](https://youtu.be/_fap9GElVeI) |
| Text — Authenticated child queries | [youtu.be/SCRv0cOu8xg](https://youtu.be/SCRv0cOu8xg) |             |
| Voice — Authenticated child queries | https://youtu.be/C9LLUnbOzUQ                         |

## Try It — Demo Script

See **[docs/demo_questions.md](docs/demo_questions.md)** for a guided walkthrough with sample questions, security codes, and edge cases to exercise both the general handbook RAG and authenticated child-specific queries.

## Run Locally

**Requires:** Python 3.11+, Node 18+, `uv`

```bash
cp .env.example .env   # add ANTHROPIC_API_KEY (required); DEEPGRAM_API_KEY + CARTESIA_API_KEY for voice
make setup             # installs deps, downloads handbook, builds FAISS index, seeds DB
```

In three terminals:

```bash
make backend           # API on :8000
make frontend          # Parent UI on :5173
make dashboard         # Operator view on :8001
```

## Tests

```bash
make test              # 61 backend (pytest) + 29 frontend (vitest)
```