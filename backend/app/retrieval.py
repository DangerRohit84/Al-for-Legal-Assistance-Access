"""Retrieval: Strategy pattern. TF-IDF when sklearn present, token-overlap fallback otherwise.

Keeps MVP zero-download and fast; swap in dense embeddings later via the same
InMemoryStore interface (Open/Closed: extend, don't modify callers).

Efficiency: bounded O(N) per search with N <= MAX_STORE_CHUNKS (5000) and
top_k clamped to 1..10. Zero-overlap filter (s > 0) guarantees the
Cannot-Determine path instead of a spurious Partial. Scores in [0, 1] are
attached to Chunk.score and surfaced in API citations for calibrated
confidence (see prompting.confidence_for).
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> list:
    return _WORD.findall((s or "").lower())


class InMemoryStore:
    """Single responsibility: hold chunks + rank by query similarity."""

    def __init__(self) -> None:
        self.chunks: list = []

    def add(self, chunks: list) -> None:
        self.chunks.extend(chunks or [])

    def clear(self) -> None:
        self.chunks = []

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

            corpus = [c.text for c in self.chunks]
            vec = TfidfVectorizer().fit_transform(corpus + [query])
            sims = cosine_similarity(vec[-1], vec[:-1])[0]
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
            qt = set(_tokens(query))
            if not qt:
                return []

            def score(c) -> float:
                ct = set(_tokens(c.text))
                if not ct:
                    return 0.0
                return len(qt & ct) / (1 + len(qt | ct))

            ranked = sorted(self.chunks, key=score, reverse=True)
            # Filter zero-overlap so unrelated queries return [] (Cannot Determine).
            hits = []
            for c in ranked[:top_k]:
                s = score(c)
                if s > 0:
                    c.score = float(s)
                    hits.append(c)
            return hits
