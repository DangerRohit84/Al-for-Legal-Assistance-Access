"""Domain models. Entities only — no I/O here (Clean Architecture).

SOLID: SRP — pure data holders; behavior lives in ingest/retrieval/prompting.
Each dataclass has one reason to change (schema evolution only).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageText:
    page: int
    text: str


@dataclass
class Chunk:
    """Retrieved unit: clause-aware slice with page metadata + retrieval score.

    score is cosine/Jaccard similarity in [0, 1] set by InMemoryStore.search().
    Default 0.0 keeps hand-constructed Chunks (tests/seeds) backward compatible.
    """

    chunk_id: str
    doc_id: str
    page: int
    clause: str
    text: str
    score: float = 0.0


@dataclass
class Document:
    doc_id: str
    filename: str
    pages: list = field(default_factory=list)
    chunks: list = field(default_factory=list)


@dataclass
class CitedAnswer:
    answer: str
    citations: list
    confidence: str  # Grounded | Partial | Cannot Determine
    disclaimer: str
