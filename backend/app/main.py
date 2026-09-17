"""FastAPI wiring (Interface Adapter): HTTP <-> use-cases. Keeps domain pure."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .actions import build_checklist, build_draft
from .config import settings
from .ingest import parse_pdf_bytes
from .llm.factory import get_provider
from .prompting import CANNOT_DETERMINE, DISCLAIMER, confidence_for, format_citations
from .retrieval import InMemoryStore
from .security import MAX_PDF_BYTES, sanitize_text, validate_pdf, validate_post_parse, validate_pre_parse

app = FastAPI(title="Clause-Grounded Legal Aid", version="0.1.0")
# Secure-by-default CORS: same-origin needs no CORS. Only enable allowlist
# when FRONTEND_ORIGIN / ALLOWED_ORIGINS is set (never "*").
if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"
    )
    return resp

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
try:
    if FRONTEND_DIR.exists():
        app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
except Exception:
    pass

# In-memory registries — DEMO single-tenant (fake/redacted docs only).
# Public multi-user prod must scope STORES per user/session and remove
# GLOBAL_STORE cross-user fallback (see docs/DEPLOYMENT.md + security-audit F1).
# Bounded by MAX_STORE_CHUNKS (429 when full) to prevent unbounded growth.
DOCS: dict = {}
STORES: dict = {}
GLOBAL_STORE = InMemoryStore()


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    doc_ids: list[str] = Field(default_factory=list, max_length=5)
    plain_language: bool = False
    top_k: int = Field(default=5, ge=1, le=10)


class CompareIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    doc_id_a: str = Field(min_length=1, max_length=128)
    doc_id_b: str = Field(min_length=1, max_length=128)
    plain_language: bool = False
    top_k: int = Field(default=3, ge=1, le=10)


class ActionIn(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    doc_ids: list[str] = Field(default_factory=list, max_length=5)


def _search(question: str, doc_ids: list, top_k: int):
    # Bound fan-out: prevents 10k-entry doc_ids CPU DoS (F5).
    doc_ids = (doc_ids or [])[: settings.max_doc_ids]
    if doc_ids:
        hits = []
        for d in doc_ids:
            store = STORES.get(d)
            if store:
                hits.extend(store.search(question, top_k=top_k))
        # re-rank merged hits by retrieval order is enough for MVP
        return hits[:top_k]
    return GLOBAL_STORE.search(question, top_k=top_k)


@app.get("/health")
def health():
    return {"status": "ok", "provider": settings.llm_provider}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    # Bounded read: never buffer more than 10 MB + 1 byte before size guard.
    # Prevents OOM on huge uploads (F3); oversize yields len > MAX -> 400.
    data = await file.read(MAX_PDF_BYTES + 1)
    filename = file.filename or "upload.pdf"
    ctype = file.content_type or "application/octet-stream"
    # DoS-safe ordering: cheap guards (extension+size+magic+type) BEFORE parse.
    try:
        validate_pre_parse(filename, ctype, len(data), data)
        # Full-entropy doc_id (122-bit uuid4 hex, not truncated 32-bit).
        doc_id = uuid.uuid4().hex
        doc = parse_pdf_bytes(data, doc_id, filename)
        validate_post_parse(len(doc.pages))
        validate_pdf(filename, ctype, len(data), len(doc.pages))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Bound global memory: refuse when shared index would grow unbounded.
    if len(GLOBAL_STORE.chunks) + len(doc.chunks) > settings.max_store_chunks:
        raise HTTPException(status_code=429, detail="Index full: restart demo or raise MAX_STORE_CHUNKS")
    store = InMemoryStore()
    store.add(doc.chunks)
    DOCS[doc_id] = doc
    STORES[doc_id] = store
    GLOBAL_STORE.add(doc.chunks)
    return {
        "doc_id": doc_id,
        "filename": filename,
        "pages": len(doc.pages),
        "chunks": len(doc.chunks),
        "preview": [ {"page": c.page, "clause": c.clause, "text": c.text[:200]} for c in doc.chunks[:5]],
    }


@app.post("/ask")
def ask(body: AskIn):
    question = sanitize_text(body.question, 1000)
    hits = _search(question, body.doc_ids, min(body.top_k, settings.max_chunks))
    provider = get_provider()
    try:
        answer = provider.answer(question, hits, plain_language=body.plain_language)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    # Hard guarantee: no hits -> Cannot Determine (even if provider hallucinates)
    if not hits:
        answer = CANNOT_DETERMINE
        confidence = "Cannot Determine"
    else:
        confidence = confidence_for(hits, len(hits))
    return {
        "answer": answer,
        "confidence": confidence,
        "citations": [
            {"doc_id": c.doc_id, "page": c.page, "clause": c.clause, "text": c.text[:500]}
            for c in hits
        ],
        "citation_line": format_citations(hits) if hits else "",
        "disclaimer": DISCLAIMER,
        "provider": provider.name,
    }


@app.post("/compare")
def compare(body: CompareIn):
    question = sanitize_text(body.question, 1000)
    a_hits = STORES.get(body.doc_id_a, InMemoryStore()).search(question, top_k=body.top_k)
    b_hits = STORES.get(body.doc_id_b, InMemoryStore()).search(question, top_k=body.top_k)
    provider = get_provider()
    return {
        "question": question,
        "side_a": {
            "doc_id": body.doc_id_a,
            "answer": provider.answer(question, a_hits, plain_language=body.plain_language) if a_hits else CANNOT_DETERMINE,
            "confidence": confidence_for(a_hits, len(a_hits)),
            "citations": [
                {"doc_id": c.doc_id, "page": c.page, "clause": c.clause, "text": c.text[:400]} for c in a_hits
            ],
        },
        "side_b": {
            "doc_id": body.doc_id_b,
            "answer": provider.answer(question, b_hits, plain_language=body.plain_language) if b_hits else CANNOT_DETERMINE,
            "confidence": confidence_for(b_hits, len(b_hits)),
            "citations": [
                {"doc_id": c.doc_id, "page": c.page, "clause": c.clause, "text": c.text[:400]} for c in b_hits
            ],
        },
        "disclaimer": DISCLAIMER,
    }


@app.post("/action-plan")
def action_plan(body: ActionIn):
    topic = sanitize_text(body.topic, 500)
    hits = _search(topic, body.doc_ids, top_k=3)
    evidence = [f"[Doc {c.doc_id} p.{c.page}, {c.clause}] {c.text[:200]}" for c in hits]
    return {
        "checklist": build_checklist(topic, evidence),
        "draft": build_draft(topic, evidence),
        "citations": [
            {"doc_id": c.doc_id, "page": c.page, "clause": c.clause, "text": c.text[:200]} for c in hits
        ],
        "disclaimer": DISCLAIMER,
    }


@app.get("/")
def root():
    idx = FRONTEND_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return JSONResponse({"message": "API running. Frontend not built yet.", "health": "/health"})
