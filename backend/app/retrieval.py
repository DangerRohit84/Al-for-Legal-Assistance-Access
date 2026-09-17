"""Retrieval: Strategy pattern. TF-IDF when sklearn present, token-overlap fallback otherwise.

Keeps MVP zero-download and fast; swap in dense embeddings later via the same
InMemoryStore interface (Open/Closed: extend, don't modify callers).

Efficiency: bounded O(N) per search with N <= MAX_STORE_CHUNKS (5000) and
top_k clamped to 1..10. TF-IDF uses a versioned cached index (fit once per
corpus version, query-only transform per search) instead of per-search
re-fit, plus single-pass scoring in the fallback. Zero-overlap filter
(s > 0) guarantees the Cannot-Determine path instead of a spurious Partial.
Scores in [0, 1] are attached to Chunk.score and surfaced in API citations
for calibrated confidence (see prompting.confidence_for).
Stop-words filtered (TF-IDF stop_words=english + fallback _STOP) so
"What is the capital of France?" scores 0.0 vs rent corpus -> [].
Thread-safe cached index via threading.Lock for concurrent /ask.
"""
from __future__ import annotations

import re
import threading

_WORD = re.compile(r"[a-z0-9]+")
# Minimal english stop-words for the zero-download fallback (mirrors sklearn
# stop_words="english" for the critical what/is/the/of/when/due inflators).
_STOP = frozenset((
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "what", "when", "where", "who", "how", "why", "of", "on", "in", "to",
    "for", "with", "and", "or", "as", "at", "by", "from", "that", "this",
    "it", "its", "due", "so", "than", "then", "there", "their", "they",
))


def _tokens(s: str) -> list:
    return _WORD.findall((s or "").lower())


def _content_tokens(s: str) -> set:
    return {t for t in _tokens(s) if t not in _STOP}


def _overlap_search(chunks: list, query: str, top_k: int) -> list:
    """Single-pass Jaccard fallback on stop-word-filtered tokens."""
    qt = _content_tokens(query)
    if not qt:
        return []
    scored = []
    for c in chunks:
        ct = _content_tokens(c.text)
        s = (len(qt & ct) / (1 + len(qt | ct))) if ct else 0.0
        scored.append((s, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    hits = []
    for s, c in scored[:top_k]:
        if s > 0:
            c.score = float(s)
            hits.append(c)
    return hits


class InMemoryStore:
    """Single responsibility: hold chunks + rank by query similarity."""

    def __init__(self) -> None:
        self.chunks: list = []
        # Versioned TF-IDF cache: fit once per corpus version, transform per query.
        self._version: int = 0
        self._vectorizer = None
        self._doc_matrix = None
        self._cache_version: int = -1
        self._lock = threading.Lock()

    def add(self, chunks: list) -> None:
        self.chunks.extend(chunks or [])
        self._version += 1
        self._vectorizer = None
        self._doc_matrix = None

    def clear(self) -> None:
        self.chunks = []
        self._version += 1
        self._vectorizer = None
        self._doc_matrix = None

    def search(self, query: str, top_k: int = 5) -> list:
        """Rank chunks by cosine/Jaccard similarity; attach Chunk.score.

        Returns top_k hits with score > 0, sorted desc. Empty list means
        zero token overlap -> callers must take the Cannot Determine path.
        """
        if not self.chunks or not (query or "").strip():
            return []
        top_k = max(1, min(top_k, 10))
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            # Cached index: refit only when corpus version changed (add/clear).
            # Per-search work is query-only transform + cosine against cached
            # doc matrix, not fit_transform(corpus + [query]) re-tokenizing N.
            # stop_words="english" drops what/is/the/of inflators so France
            # query scores 0.0 -> [] -> Cannot Determine (not 0.50 Grounded).
            # Lock guards concurrent refit on first search after add/clear.
            with self._lock:
                if self._vectorizer is None or self._doc_matrix is None or self._cache_version != self._version:
                    corpus = [c.text for c in self.chunks]
                    self._vectorizer = TfidfVectorizer(stop_words="english")
                    self._doc_matrix = self._vectorizer.fit_transform(corpus)
                    self._cache_version = self._version
                q_vec = self._vectorizer.transform([query])
                sims = cosine_similarity(q_vec, self._doc_matrix)[0]
            ranked = sorted(zip(sims, self.chunks), key=lambda x: x[0], reverse=True)
            hits: list = []
            for s, c in ranked[:top_k]:
                if float(s) > 0:
                    c.score = float(s)
                    hits.append(c)
            # Return possibly-empty hits so callers hit the Cannot Determine
            # path instead of a spurious Partial on zero token overlap.
            return hits
        except ImportError:
            return _overlap_search(self.chunks, query, top_k)
        except ValueError:
            # Empty vocabulary (e.g., stop-words-only corpus): fall back to overlap.
            return _overlap_search(self.chunks, query, top_k)
