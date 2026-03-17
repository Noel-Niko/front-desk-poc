# Handbook RAG Pipeline

How the handbook search system works in `backend/app/services/handbook.py`.

## What problem does this solve?

The AI front desk assistant needs to answer parent questions about center policies (drop-off times, allergy procedures, fees, etc.). The handbook PDF contains all these answers, but an LLM can't read a PDF directly at query time — and even if it could, stuffing the entire document into every prompt is wasteful and slow.

**RAG (Retrieval-Augmented Generation)** solves this: instead of sending the whole handbook, we search for the 3–5 most relevant passages and inject only those into the LLM prompt. The LLM gets targeted context and can cite specific pages.

## Architecture overview

```
┌──────────────┐
│ Handbook PDF  │
└──────┬───────┘
       │  (first run only)
       ▼
┌──────────────┐     ┌───────────────────┐
│ Extract text │────▶│ Split into chunks  │
│  (PyMuPDF)   │     │ (~300 words each)  │
└──────────────┘     └────────┬──────────┘
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
        ┌────────────────┐       ┌──────────────────┐
        │ Embed chunks   │       │ Tokenize chunks   │
        │ (MiniLM → 384d)│       │ (whitespace split) │
        └───────┬────────┘       └────────┬──────────┘
                │                         │
                ▼                         ▼
        ┌────────────────┐       ┌──────────────────┐
        │  FAISS index   │       │   BM25 index     │
        │ (vector search)│       │ (keyword search)  │
        └───────┬────────┘       └────────┬──────────┘
                │                         │
                │    ┌─────────────┐      │
                └───▶│  RRF Fusion │◀─────┘
                     │ (merge rank)│
                     └──────┬──────┘
                            ▼
                    Top-K chunks returned
                     to the LLM prompt
```

## Step-by-step: Building the index

### 1. PDF text extraction (`_extract_text_from_pdf`)

Uses PyMuPDF to read each page and pull out raw text. Returns a list of `(page_number, text)` tuples. Page numbers are 1-indexed so they match the actual PDF page numbers for citations.

### 2. Chunking (`_chunk_pages`)

A full page of text is too large to be a useful search result — you'd return too much noise. Instead, we split each page into **overlapping windows** of roughly 300 words.

```
Page text:  [word1 word2 word3 ... word600]

Chunk 0:    [word1   ──────── word300]
Chunk 1:            [word250 ──────── word550]    ← 50-word overlap
Chunk 2:                    [word500 ── word600]
```

**Why overlap?** If a relevant sentence falls right at a chunk boundary, the overlap ensures it appears in full in at least one chunk. Without overlap, you'd split sentences in half and miss matches.

Each chunk keeps metadata:
- `chunk_id` — unique identifier (e.g. `chunk_42`)
- `text` — the actual passage
- `page_number` — for citation back to the PDF
- `section_title` — rough guess from the first line of the page

### 3. Embedding (SentenceTransformer → FAISS)

This is the core of **semantic search** — finding passages that are conceptually similar to a query, even if they don't share exact keywords.

**What is an embedding?** A function that maps text to a fixed-size vector (array of numbers) in a way that preserves meaning:

```
"What are the drop-off hours?"  →  [0.12, -0.45, 0.78, ..., 0.33]  (384 numbers)
"Morning arrival time is 8 AM"  →  [0.11, -0.43, 0.76, ..., 0.31]  (similar vector!)
"The fee for late pickup is $5" →  [0.89, 0.22, -0.15, ..., 0.67]  (different vector)
```

Texts with similar meaning end up close together in this 384-dimensional space. The model used is `all-MiniLM-L6-v2` — a small (22M parameter) but effective sentence transformer.

**FAISS** (Facebook AI Similarity Search) stores all chunk vectors and can efficiently find the nearest neighbors to a query vector. The specific index type is `IndexFlatIP`:

- **Flat** = brute-force, compares against every vector (no approximation). Fine for hundreds of chunks, wouldn't scale to millions.
- **IP** = inner product similarity. Since the vectors are L2-normalized (`normalize_embeddings=True`), inner product equals cosine similarity.

### 4. BM25 (keyword search)

BM25 (Best Matching 25) is a classic information retrieval algorithm. Think of it as a smarter version of "count how many query words appear in each document," with two refinements:

- **Term frequency saturation** — the 10th occurrence of "allergy" in a chunk doesn't help much more than the 3rd
- **Inverse document frequency** — rare words ("anaphylaxis") matter more than common words ("the")

BM25 catches cases where semantic search might fail — exact names, specific codes, or uncommon terms that the embedding model hasn't seen before.

### 5. Disk caching

After the first build, the FAISS index and chunk metadata are saved to disk:

```
backend/data/handbook_index/
├── faiss.index    ← serialized FAISS vector index
└── chunks.json    ← chunk text + metadata
```

On subsequent startups, these are loaded directly instead of re-extracting and re-embedding. BM25 is rebuilt in memory each time because it's cheap (just tokenization + counting).

## Step-by-step: Querying at runtime

### `hybrid_search` — Reciprocal Rank Fusion

When a parent asks "What's the allergy policy?", the system runs **both** search methods and merges the results:

1. **FAISS semantic search** returns chunks ranked by vector similarity
2. **BM25 keyword search** returns chunks ranked by term overlap

The two ranked lists are merged using **Reciprocal Rank Fusion (RRF)**:

```
score(chunk) = (0.7 / (60 + semantic_rank + 1)) + (0.3 / (60 + bm25_rank + 1))
```

- A chunk ranked #1 in semantic gets: `0.7 / 62 = 0.0113`
- A chunk ranked #1 in BM25 gets: `0.3 / 62 = 0.0048`
- A chunk ranked #1 in **both** gets: `0.0113 + 0.0048 = 0.0161` (boosted)

The weights (0.7 semantic / 0.3 BM25) mean semantic similarity is favored, but keyword matches still contribute. The constant `k=60` dampens the effect of rank position — the difference between rank #1 and #5 is smaller than you'd think, preventing any single method from dominating.

### Why hybrid instead of just one method?

| Query type | Semantic wins | BM25 wins |
|---|---|---|
| "What do I do if my child is sick?" | Finds "illness policy" passages even though "sick" ≠ "illness" | Might miss if the handbook says "illness" everywhere |
| "Dr. Martinez contact number" | Might not understand proper nouns well | Exact keyword match finds it immediately |
| "Tell me about peanut allergies" | Understands "peanut allergies" ≈ "nut-free policy" | Also matches on "allergy" keyword directly |

Hybrid search gives you the best of both.

## Key design decisions

| Decision | Choice | Why |
|---|---|---|
| Embedding model | `all-MiniLM-L6-v2` | Small, fast, good quality for English sentence similarity. Runs on CPU. |
| FAISS index type | `IndexFlatIP` (brute force) | Exact results, no tuning needed. Only ~100 chunks, so brute force is fine. |
| Chunk size | ~300 words | Large enough for context, small enough for precision. |
| Overlap | 50 words | Prevents losing info at chunk boundaries. |
| Fusion method | RRF | Simple, parameter-free (no score normalization needed), well-studied. |
| Caching | FAISS + JSON on disk | Avoids re-embedding on every restart. BM25 is fast enough to rebuild. |

## Glossary

| Term | Meaning |
|---|---|
| **RAG** | Retrieval-Augmented Generation — fetch relevant docs, then generate an answer using them as context |
| **Embedding** | A dense vector representation of text that captures semantic meaning |
| **FAISS** | Facebook AI Similarity Search — a library for fast nearest-neighbor search over vectors |
| **BM25** | A probabilistic keyword ranking algorithm (the backbone of traditional search engines) |
| **RRF** | Reciprocal Rank Fusion — a method for combining multiple ranked lists into one |
| **Cosine similarity** | Measures the angle between two vectors; 1.0 = identical direction, 0.0 = orthogonal |
| **IndexFlatIP** | A FAISS index that does exact (brute-force) inner product search |
| **SentenceTransformer** | A Python library for generating sentence/paragraph embeddings from transformer models |
