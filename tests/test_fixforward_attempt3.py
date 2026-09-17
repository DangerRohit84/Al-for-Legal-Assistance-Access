"""Attempt-3 fix-forward regression: stop-word irrelevance, DEMO guard, cache.

Proves senior-dev diagnosis:
- France stop-word query scored 0.50 Grounded -> now [] -> Cannot Determine
- DEMO_MODE guard matrix (prod closes GLOBAL leak, demo keeps video stability)
- Cached TF-IDF repeat faster than refit (efficiency, no cold-start regression)
"""
from __future__ import annotations

import io
import time

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.main import app
from backend.app.models import Chunk
from backend.app.prompting import CANNOT_DETERMINE


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


RENT = [
    "Clause 5.1 Rent is due on the 5th of every month.",
    "Clause 5.2 Late fee of Rs 500 applies after the 10th.",
    "Clause 9 Termination needs 30 days written notice.",
]


def _upload(client: TestClient, lines=RENT, filename="rent.pdf", session: str = "") -> dict:
    headers = {"X-Demo-Session": session} if session else {}
    r = client.post(
        "/upload",
        files={"file": (filename, _make_pdf_bytes(lines), "application/pdf")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_unrelated_stopword_query_returns_cannot_determine(client):
    """France query shares only what/is/the/of with rent corpus -> [] -> refusal."""
    from backend.app.retrieval import InMemoryStore, _overlap_search

    store = InMemoryStore()
    store.add(
        [
            Chunk("a", "d", 1, "Clause 5.1", "Rent is due on the 5th of every month."),
            Chunk("b", "d", 1, "Clause 5.2", "Late fee of Rs 500 applies after the 10th."),
            Chunk("c", "d", 1, "Clause 9", "Termination needs 30 days written notice."),
        ]
    )
    # TF-IDF path (sklearn present): stop_words=english kills inflators.
    hits = store.search("What is the capital of France?", top_k=5)
    assert hits == [], f"stop-word query must be [] not {[(h.chunk_id, h.score) for h in hits]}"
    # Fallback helper path: same guarantee without sklearn.
    assert _overlap_search(store.chunks, "What is the capital of France?", 5) == []
    # Relevant query still grounds (no over-filtering).
    assert store.search("when is rent due?", top_k=5), "rent query must still hit"
    # E2E via API: doc_ids path -> hard Cannot Determine override.
    doc = _upload(client)
    r = client.post(
        "/ask",
        json={"question": "What is the capital of France?", "doc_ids": [doc["doc_id"]]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["citations"] == []
    assert body["confidence"] == "Cannot Determine"
    assert body["answer"] == CANNOT_DETERMINE


def test_stopword_only_query_returns_cannot_determine():
    """Query of only stop-words (what/is/the) -> [] on both paths."""
    from backend.app.retrieval import InMemoryStore, _overlap_search

    store = InMemoryStore()
    store.add([Chunk("a", "d", 1, "Clause 1", "Rent is due on the 5th monthly")])
    assert store.search("what is the?", top_k=3) == []
    assert _overlap_search(store.chunks, "what is the?", 3) == []


def test_demo_guard_matrix(client):
    """DEMO_MODE x session matrix: demo keeps video stability, prod closes leak."""
    old_demo = main_module.settings.demo_mode
    try:
        # Seed GLOBAL_STORE via header-less upload (single-tenant demo path).
        doc = _upload(client)
        # 1) DEMO_MODE=true, no session, no doc_ids -> GLOBAL fallback hits.
        main_module.settings.demo_mode = "true"
        hit = client.post("/ask", json={"question": "When is rent due?"})
        assert hit.status_code == 200
        assert hit.json()["citations"], "demo global fallback must hit for video stability"
        assert hit.json()["confidence"] in ("Partial", "Grounded")
        # 2) DEMO_MODE=false, no session, no doc_ids -> [] -> Cannot Determine.
        main_module.settings.demo_mode = "false"
        miss = client.post("/ask", json={"question": "When is rent due?"})
        assert miss.status_code == 200
        assert miss.json()["citations"] == []
        assert miss.json()["confidence"] == "Cannot Determine"
        assert miss.json()["answer"] == CANNOT_DETERMINE
        # 3) Explicit doc_ids bypass guard in both modes (bounded fan-out).
        main_module.settings.demo_mode = "false"
        direct = client.post(
            "/ask", json={"question": "When is rent due?", "doc_ids": [doc["doc_id"]]}
        )
        assert direct.json()["citations"], "explicit doc_ids must work in prod too"
        main_module.settings.demo_mode = "true"
        direct2 = client.post(
            "/ask", json={"question": "When is rent due?", "doc_ids": [doc["doc_id"]]}
        )
        assert direct2.json()["citations"]
        # 4) Session isolation holds regardless of DEMO_MODE.
        main_module.DOCS.clear()
        main_module.STORES.clear()
        main_module.GLOBAL_STORE.clear()
        main_module.SESSION_STORES.clear()
        _upload(client, session="sess-a")
        for mode in ("true", "false"):
            main_module.settings.demo_mode = mode
            same = client.post(
                "/ask",
                json={"question": "When is rent due?"},
                headers={"X-Demo-Session": "sess-a"},
            )
            assert same.json()["citations"], f"sess-a must see own docs (mode={mode})"
            other = client.post(
                "/ask",
                json={"question": "When is rent due?"},
                headers={"X-Demo-Session": "sess-b"},
            )
            assert other.json()["citations"] == []
            assert other.json()["confidence"] == "Cannot Determine"
    finally:
        main_module.settings.demo_mode = old_demo
        main_module.DOCS.clear()
        main_module.STORES.clear()
        main_module.GLOBAL_STORE.clear()
        main_module.SESSION_STORES.clear()


def test_cached_repeat_faster_than_refit():
    """Versioned cache: repeat transform+cosine cheaper than fit_transform."""
    from backend.app.retrieval import InMemoryStore

    store = InMemoryStore()
    store.add(
        [Chunk(f"c{i}", "d", (i % 10) + 1, f"Clause {i}", f"rent agreement clause {i} payment notice") for i in range(200)]
    )
    q = "when is rent due?"
    # Cold: first search fits index.
    t0 = time.perf_counter()
    cold = store.search(q, top_k=5)
    t_cold = time.perf_counter() - t0
    assert cold, "expected hits at MVP scale"
    assert t_cold < 1.0, f"cold search too slow: {t_cold:.3f}s"
    vec_id = id(store._vectorizer)
    assert store._cache_version == store._version
    # Warm: repeats reuse cached matrix (no refit).
    times = []
    for _ in range(5):
        t1 = time.perf_counter()
        warm = store.search(q, top_k=5)
        times.append(time.perf_counter() - t1)
        assert [h.chunk_id for h in warm] == [h.chunk_id for h in cold]
        assert id(store._vectorizer) == vec_id, "repeat must reuse cached vectorizer"
    t_warm = sum(times) / len(times)
    assert t_warm < 1.0, f"warm search too slow: {t_warm:.3f}s"
    # Cached repeat must not be slower than cold fit (allow 20% noise).
    assert t_warm <= t_cold * 1.2 + 0.005, f"cache regression: warm {t_warm:.4f}s > cold {t_cold:.4f}s"
