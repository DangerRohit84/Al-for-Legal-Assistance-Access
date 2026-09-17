"""Retrieval: Strategy pattern. TF-IDF when sklearn present, token-overlap fallback otherwise.

Keeps MVP zero-download and fast; swap in dense embeddings later via the same
InMemoryStore interface (Open/Closed: extend, don't modify callers).
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
            hits = [c for s, c in ranked[:top_k] if s > 0]
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
            return [c for c in ranked[:top_k] if score(c) > 0]
