"""Security guardrails: upload validation. Single responsibility only."""
from __future__ import annotations

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 100
# Strict allowlist: octet-stream accepted only at transport layer, but magic
# bytes (%PDF-) are authoritative. See validate_pdf_magic() below.
ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}
STRICT_CONTENT_TYPES = {"application/pdf"}
PDF_MAGIC = b"%PDF-"


def validate_pdf_magic(data: bytes) -> bool:
    """Magic-byte check: data must start with %PDF-. Raises ValueError."""
    if not data or data[:5] != PDF_MAGIC:
        raise ValueError("Invalid PDF: missing %PDF- magic header")
    return True


def validate_pre_parse(filename: str, content_type: str, size_bytes: int, data: bytes) -> bool:
    """Cheap guards BEFORE pypdf parse (DoS-safe ordering).

    Order: extension -> size -> magic bytes -> strict content-type hint.
    Raises ValueError with user-safe message.
    """
    if not filename or not filename.lower().endswith(".pdf"):
        raise ValueError("PDF only: file must end with .pdf")
    if size_bytes > MAX_PDF_BYTES:
        raise ValueError("File too large: max 10 MB")
    if size_bytes <= 0:
        raise ValueError("Empty file: upload a valid PDF")
    validate_pdf_magic(data)
    # octet-stream tolerated (some browsers/clients), but warn path stays;
    # strict mode rejects non-PDF content-types outright.
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("PDF only: invalid content-type")
    return True


def validate_post_parse(num_pages: int) -> bool:
    """Page-count guards AFTER parse. Raises ValueError."""
    if num_pages > MAX_PDF_PAGES:
        raise ValueError("Too many pages: max 100 pages in MVP")
    if num_pages < 1:
        raise ValueError("Unreadable PDF: no pages found")
    return True


def validate_pdf(filename: str, content_type: str, size_bytes: int, num_pages: int) -> bool:
    """Validate an uploaded PDF. Raises ValueError with user-safe message."""
    if not filename or not filename.lower().endswith(".pdf"):
        raise ValueError("PDF only: file must end with .pdf")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("PDF only: invalid content-type")
    if size_bytes > MAX_PDF_BYTES:
        raise ValueError("File too large: max 10 MB")
    if size_bytes <= 0:
        raise ValueError("Empty file: upload a valid PDF")
    if num_pages > MAX_PDF_PAGES:
        raise ValueError("Too many pages: max 100 pages in MVP")
    if num_pages < 1:
        raise ValueError("Unreadable PDF: no pages found")
    return True


def sanitize_text(text: str, limit: int = 2000) -> str:
    """Trim + strip control chars for safe echo into prompts/logs."""
    cleaned = "".join(ch for ch in (text or "") if ch.isprintable() or ch in ("\n", "\t"))
    return cleaned.strip()[:limit]
