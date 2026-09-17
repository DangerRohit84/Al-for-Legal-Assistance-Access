"""Efficiency regression: prove bounded, fast, zero-download MVP.

Covers MED->HIGH: chunk caps, top_k clamp, bounded index 429,
sub-second search, lazy optional deps, process-time + rate-limit headers,
bounded upload read.
"""
from __future__ import annotations

import io
import time

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.ingest import MAX_CHUNK_CHARS, chunk_pages
from backend.app.models import Chunk, PageText
from backend.app.main import app


@pytest.fixture()
def client():
    main_module.DOCS.clear()
    main_module.STORES.clear()
    main_module.GLOBAL_STORE.clear()
    main_module.SESSION_STORES.clear()
    main_module._RATE_BUCKETS.clear()
    with TestClient(app) as c:
        yield c
    main_module.DOCS.clear()
    main_module.STORES.clear()
    main_module.GLOBAL_STORE.clear()
    main_module.SESSION_STORES.clear()
    main_module._RATE_BUCKETS.clear()


def _make_pdf_bytes(lines: list[str]) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 750
    for line in lines:
        c.drawString(72, y, line)
        y -= 20
    c.showPage()
    c.save()
    return buf.getvalue()


def test_chunk_bound_enforced():
    assert MAX_CHUNK_CHARS <= 1500
    pages = [PageText(page=1, text="Clause 1.1 " + ("x" * 5000))]
    chunks = chunk_pages(pages, doc_id="d")
    assert chunks
    for ch in chunks:
        assert len(ch.text) <= 1500


def test_top_k_clamped_to_10():
    from backend.app.retrieval import InMemoryStore

    store = InMemoryStore()
    store.add([Chunk(f"c{i}", "d", 1, f"Clause {i}", f"rent due clause number {i} token") for i in range(20)])
    hits = store.search("rent due", top_k=100)
    assert 0 < len(hits) <= 10


def test_bounded_index_returns_429_when_full(client):
    old = main_module.settings.max_store_chunks
    main_module.settings.max_store_chunks = 3
    try:
        r1 = client.post(
            "/upload",
            files={"file": ("a.pdf", _make_pdf_bytes(["Clause 1 Rent due 5th."]), "application/pdf")},
        )
        assert r1.status_code == 200, r1.text
        # second upload would exceed 3 chunks -> 429, not OOM
        r2 = client.post(
            "/upload",
            files={
                (
                    "file"
                ): (
                    "b.pdf",
                    _make_pdf_bytes(
                        [
                            "Clause 1 Rent due 5th.",
                            "Clause 2 Late fee Rs 500.",
                            "Clause 3 Notice 30 days.",
                            "Clause 4 Extra term here.",
                        ]
                    ),
                    "application/pdf",
                )
            },
        )
        assert r2.status_code == 429
        assert "Index full" in r2.json()["detail"]
    finally:
        main_module.settings.max_store_chunks = old
        main_module.DOCS.clear()
        main_module.STORES.clear()
        main_module.GLOBAL_STORE.clear()


def test_search_sub_second_at_mvp_scale():
    from backend.app.retrieval import InMemoryStore

    store = InMemoryStore()
    store.add(
        [Chunk(f"c{i}", "d", (i % 10) + 1, f"Clause {i}", f"rent agreement clause {i} payment due notice") for i in range(200)]
    )
    t0 = time.time()
    hits = store.search("when is rent due?", top_k=5)
    dt = time.time() - t0
    assert hits
    assert dt < 1.0, f"search too slow: {dt:.3f}s"


def test_lazy_optional_deps():
    # retrieval works with zero-download fallback (no sklearn required)
    from backend.app.retrieval import InMemoryStore

    store = InMemoryStore()
    store.add([Chunk("a", "d", 1, "Clause 1", "rent due monthly")])
    assert store.search("rent due", top_k=1)
    # echo provider needs no network/key
    from backend.app.llm.factory import get_provider

    prov = get_provider("echo")
    assert prov.answer("q", []) == "Cannot Determine from the provided documents."


def test_process_time_header_present(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("X-Process-Time"), "efficiency transparency header missing"
    assert r.headers.get("X-Process-Time", "").endswith("s")


def test_rate_limit_headers_present_on_api(client):
    r = client.get("/health")
    assert r.headers.get("X-RateLimit-Limit")
    assert r.headers.get("X-RateLimit-Remaining") is not None
    assert r.headers.get("X-RateLimit-Reset")


def test_bounded_oversize_rejects_without_oom(client):
    big = b"%PDF-1.4 fake" + b"x" * (11 * 1024 * 1024)
    r = client.post("/upload", files={"file": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 400
    assert "10 MB" in r.json()["detail"]
