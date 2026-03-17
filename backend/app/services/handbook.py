"""Handbook RAG service: hybrid FAISS + BM25 search with page-level citations."""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SIZE_TOKENS = 300  # approximate words
CHUNK_OVERLAP_TOKENS = 50


@dataclass
class HandbookChunk:
    """A single passage from the handbook with metadata."""

    chunk_id: str
    text: str
    page_number: int
    section_title: str


@dataclass
class HandbookIndex:
    """Hybrid FAISS + BM25 index over handbook chunks."""

    chunks: list[HandbookChunk] = field(default_factory=list)
    _faiss_index: faiss.IndexFlatIP | None = None
    _bm25: BM25Okapi | None = None
    _embed_model: SentenceTransformer | None = None

    def semantic_search(self, query: str, top_k: int = 5) -> list[HandbookChunk]:
        """Search using semantic similarity (FAISS)."""
        if self._faiss_index is None or self._embed_model is None:
            return []
        query_vec = self._embed_model.encode([query], normalize_embeddings=True)
        scores, indices = self._faiss_index.search(
            np.array(query_vec, dtype=np.float32), top_k
        )
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            results.append(self.chunks[idx])
        return results

    def keyword_search(self, query: str, top_k: int = 5) -> list[HandbookChunk]:
        """Search using BM25 keyword matching."""
        if self._bm25 is None:
            return []
        tokens = query.lower().split()
        scores = self._bm25.get_scores(tokens)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [self.chunks[i] for i in top_indices if scores[i] > 0]


def _extract_text_from_pdf(pdf_path: str) -> list[tuple[int, str]]:
    """Extract text from each page of the PDF. Returns list of (page_num, text)."""
    import pymupdf

    pages: list[tuple[int, str]] = []
    doc = pymupdf.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        if text.strip():
            pages.append((page_num + 1, text))  # 1-indexed pages
    doc.close()
    logger.info("Extracted text from %d pages", len(pages))
    return pages


def _guess_section_title(text: str) -> str:
    """Extract a rough section title from the first line of text."""
    lines = text.strip().split("\n")
    for line in lines[:3]:
        clean = line.strip()
        if len(clean) > 5 and len(clean) < 100:
            return clean
    return "General"


def _chunk_pages(
    pages: list[tuple[int, str]],
    chunk_size: int = CHUNK_SIZE_TOKENS,
    overlap: int = CHUNK_OVERLAP_TOKENS,
) -> list[HandbookChunk]:
    """Split page text into overlapping chunks with metadata."""
    chunks: list[HandbookChunk] = []
    chunk_id = 0

    for page_num, page_text in pages:
        words = page_text.split()
        if not words:
            continue

        section_title = _guess_section_title(page_text)
        start = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            # Clean up excessive whitespace
            chunk_text = re.sub(r"\s+", " ", chunk_text).strip()

            if len(chunk_text) > 20:  # Skip tiny fragments
                chunks.append(
                    HandbookChunk(
                        chunk_id=f"chunk_{chunk_id}",
                        text=chunk_text,
                        page_number=page_num,
                        section_title=section_title,
                    )
                )
                chunk_id += 1

            start += chunk_size - overlap

    logger.info("Created %d chunks from %d pages", len(chunks), len(pages))
    return chunks


def build_index(pdf_path: str, index_dir: str) -> HandbookIndex:
    """Build a hybrid FAISS + BM25 index from the handbook PDF.

    Caches the index to disk. If already cached, loads from disk.
    """
    index_path = Path(index_dir)
    faiss_file = index_path / "faiss.index"
    chunks_file = index_path / "chunks.json"

    # Load embedding model
    logger.info("Loading embedding model: %s", EMBED_MODEL_NAME)
    embed_model = SentenceTransformer(EMBED_MODEL_NAME)

    # Check cache
    if faiss_file.exists() and chunks_file.exists():
        logger.info("Loading cached index from %s", index_dir)
        chunks_data = json.loads(chunks_file.read_text())
        chunks = [HandbookChunk(**c) for c in chunks_data]
        faiss_index = faiss.read_index(str(faiss_file))

        # Rebuild BM25 (fast, not worth caching)
        tokenized = [c.text.lower().split() for c in chunks]
        bm25 = BM25Okapi(tokenized)

        idx = HandbookIndex(
            chunks=chunks,
            _faiss_index=faiss_index,
            _bm25=bm25,
            _embed_model=embed_model,
        )
        logger.info("Index loaded: %d chunks", len(chunks))
        return idx

    # Build from scratch
    logger.info("Building index from PDF: %s", pdf_path)
    pages = _extract_text_from_pdf(pdf_path)
    chunks = _chunk_pages(pages)

    # Embed all chunks
    texts = [c.text for c in chunks]
    logger.info("Embedding %d chunks...", len(texts))
    embeddings = embed_model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    embeddings_np = np.array(embeddings, dtype=np.float32)

    # Build FAISS index (inner product on normalized vectors = cosine similarity)
    dim = embeddings_np.shape[1]
    faiss_index = faiss.IndexFlatIP(dim)
    faiss_index.add(embeddings_np)

    # Build BM25 index
    tokenized = [c.text.lower().split() for c in chunks]
    bm25 = BM25Okapi(tokenized)

    # Cache to disk
    index_path.mkdir(parents=True, exist_ok=True)
    faiss.write_index(faiss_index, str(faiss_file))
    chunks_json = [
        {"chunk_id": c.chunk_id, "text": c.text,
         "page_number": c.page_number, "section_title": c.section_title}
        for c in chunks
    ]
    chunks_file.write_text(json.dumps(chunks_json))
    logger.info("Index saved to %s", index_dir)

    return HandbookIndex(
        chunks=chunks,
        _faiss_index=faiss_index,
        _bm25=bm25,
        _embed_model=embed_model,
    )


def hybrid_search(
    index: HandbookIndex,
    query: str,
    top_k: int = 5,
    semantic_weight: float = 0.7,
    bm25_weight: float = 0.3,
    rrf_k: int = 60,
) -> list[HandbookChunk]:
    """Reciprocal rank fusion of semantic + keyword search results."""
    semantic_results = index.semantic_search(query, top_k=top_k * 2)
    bm25_results = index.keyword_search(query, top_k=top_k * 2)

    scores: dict[str, float] = {}
    chunk_map: dict[str, HandbookChunk] = {}

    for rank, chunk in enumerate(semantic_results):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + semantic_weight / (rrf_k + rank + 1)
        chunk_map[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(bm25_results):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + bm25_weight / (rrf_k + rank + 1)
        chunk_map[chunk.chunk_id] = chunk

    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [chunk_map[cid] for cid in sorted_ids[:top_k]]
