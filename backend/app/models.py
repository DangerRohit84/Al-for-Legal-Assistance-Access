"""Domain models. Entities only — no I/O here (Clean Architecture)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageText:
    page: int
    text: str


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    page: int
    clause: str
    text: str


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
