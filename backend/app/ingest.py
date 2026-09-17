"""PDF ingest: bytes -> pages -> clause-aware chunks with page metadata.

SRP: parsing + clause splitting only. Page numbers preserved on every Chunk
(≤1500 chars) so citations [Doc p.X, Clause Y] stay traceable.
"""
from __future__ import annotations

import io
import re

from .models import Chunk, Document, PageText

CLAUSE_RE = re.compile(
    r"(Clause\s+\d+(?:\.\d+)*|Section\s+\d+(?:\.\d+)*|Article\s+\d+|Rule\s+\d+)",
    re.IGNORECASE,
)
MAX_CHUNK_CHARS = 1500


def chunk_pages(pages: list, doc_id: str = "doc") -> list:
    """Split pages on clause markers; preserve page numbers always."""
    chunks: list = []
    for p in pages:
        text = (p.text or "").strip()
        if not text:
            continue
        parts = CLAUSE_RE.split(text)
        if len(parts) <= 1:
            chunks.append(
                Chunk(f"{doc_id}-p{p.page}-c0", doc_id, p.page, f"p.{p.page}", text[:MAX_CHUNK_CHARS])
            )
            continue
        preamble = parts[0].strip()
        if preamble:
            chunks.append(
                Chunk(
                    f"{doc_id}-p{p.page}-c0",
                    doc_id,
                    p.page,
                    f"p.{p.page} preamble",
                    preamble[:MAX_CHUNK_CHARS],
                )
            )
        for i in range(1, len(parts), 2):
            label = parts[i].strip()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            merged = f"{label} {body}".strip()[:MAX_CHUNK_CHARS]
            if merged:
                chunks.append(
                    Chunk(f"{doc_id}-p{p.page}-c{i // 2 + 1}", doc_id, p.page, label, merged)
                )
    return chunks


def parse_pdf_bytes(data: bytes, doc_id: str, filename: str = "upload.pdf") -> Document:
    """Parse PDF bytes with pypdf. Raises ValueError on unreadable input."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ValueError("PDF support missing: install pypdf") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise ValueError("Unreadable PDF: could not parse file") from exc
    pages = []
    for i, pg in enumerate(reader.pages):
        try:
            txt = pg.extract_text() or ""
        except Exception:
            txt = ""
        pages.append(PageText(page=i + 1, text=txt.strip()))
    return Document(doc_id=doc_id, filename=filename, pages=pages, chunks=chunk_pages(pages, doc_id))
