"""API integration tests: upload -> ask -> compare -> action-plan wiring.

Covers main.py happy paths, validation errors, and regression tests for
FIX-1 (plain_language E2E), FIX-2 (compare citations + doc_id), and
FIX-4 (retrieval zero-overlap -> Cannot Determine).
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.main import app


@pytest.fixture()
def client():
    """Isolated TestClient with fresh in-memory stores per test."""
    main_module.DOCS.clear()
    main_module.STORES.clear()
    main_module.GLOBAL_STORE.clear()
    with TestClient(app) as c:
        yield c
    main_module.DOCS.clear()
    main_module.STORES.clear()
    main_module.GLOBAL_STORE.clear()


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


RENT_LINES = [
    "Clause 5.1 Rent is due on the 5th of every month.",
    "Clause 5.2 Late fee of Rs 500 applies after the 10th.",
    "Clause 9 Termination needs 30 days written notice.",
]

RIGHTS_LINES = [
    "Clause 5.1 Rent receipt must be issued for every payment.",
    "Section 2 Tenant rights include notice before eviction.",
]


def _upload(client: TestClient, pdf_bytes: bytes, filename: str = "rent.pdf") -> dict:
    resp = client.post(
        "/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_root_serves_frontend_or_json(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_upload_accepts_valid_pdf(client):
    body = _upload(client, _make_pdf_bytes(RENT_LINES))
    assert body["doc_id"]
    assert body["pages"] >= 1
    assert body["chunks"] >= 2
    assert len(body["preview"]) >= 1


def test_upload_rejects_non_pdf_extension(client):
    resp = client.post(
        "/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400
    assert "PDF only" in resp.json()["detail"]


def test_upload_rejects_oversize(client):
    big = b"%PDF-1.4 fake" + b"x" * (11 * 1024 * 1024)
    resp = client.post(
        "/upload",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert resp.status_code == 400
    assert "10 MB" in resp.json()["detail"]


def test_ask_returns_grounded_answer_with_citations(client):
    doc = _upload(client, _make_pdf_bytes(RENT_LINES))
    resp = client.post(
        "/ask",
        json={"question": "When is rent due?", "doc_ids": [doc["doc_id"]]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] in ("Partial", "Grounded")
    assert body["citations"], "expected at least one citation"
    first = body["citations"][0]
    assert first["doc_id"] == doc["doc_id"]
    assert "Clause" in first["clause"]
    assert "not legal advice" in body["disclaimer"].lower()
    assert "Cannot Determine" not in body["answer"]


def test_ask_cannot_determine_for_unknown_doc(client):
    resp = client.post(
        "/ask",
        json={"question": "When is rent due?", "doc_ids": ["nonexistent"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] == "Cannot Determine"
    assert body["answer"] == "Cannot Determine from the provided documents."


def test_ask_cannot_determine_for_zero_overlap(client):
    """FIX-4 regression: unrelated query vs real corpus must not be Partial."""
    doc = _upload(client, _make_pdf_bytes(RENT_LINES))
    resp = client.post(
        "/ask",
        json={
            "question": "Quantum astrophysics xyzzy plugh blorpt nebula?",
            "doc_ids": [doc["doc_id"]],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] == "Cannot Determine"
    assert body["answer"] == "Cannot Determine from the provided documents."
    assert body["citations"] == []


def test_ask_plain_language_differs_end_to_end(client):
    """FIX-1 regression: plain_language flag must change provider output."""
    doc = _upload(client, _make_pdf_bytes(RENT_LINES))
    base = {"question": "When is rent due?", "doc_ids": [doc["doc_id"]]}
    plain_off = client.post("/ask", json={**base, "plain_language": False})
    plain_on = client.post("/ask", json={**base, "plain_language": True})
    assert plain_off.status_code == 200
    assert plain_on.status_code == 200
    assert plain_off.json()["answer"] != plain_on.json()["answer"]
    assert "plain language" in plain_on.json()["answer"].lower()


def test_compare_returns_both_sides_with_doc_id_citations(client):
    """FIX-2 regression: compare citations must include doc_id like /ask."""
    doc_a = _upload(client, _make_pdf_bytes(RENT_LINES), "rent.pdf")
    doc_b = _upload(client, _make_pdf_bytes(RIGHTS_LINES), "rights.pdf")
    resp = client.post(
        "/compare",
        json={
            "question": "When is rent due?",
            "doc_id_a": doc_a["doc_id"],
            "doc_id_b": doc_b["doc_id"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    for side_key, doc in (("side_a", doc_a), ("side_b", doc_b)):
        side = body[side_key]
        assert side["doc_id"] == doc["doc_id"]
        assert side["citations"], f"{side_key} should cite clauses"
        for cite in side["citations"]:
            assert cite["doc_id"] == doc["doc_id"]
            assert "page" in cite and "clause" in cite and "text" in cite
    assert "not legal advice" in body["disclaimer"].lower()


def test_compare_unknown_doc_returns_cannot_determine(client):
    resp = client.post(
        "/compare",
        json={
            "question": "When is rent due?",
            "doc_id_a": "missing-a",
            "doc_id_b": "missing-b",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["side_a"]["confidence"] == "Cannot Determine"
    assert body["side_b"]["confidence"] == "Cannot Determine"


def test_compare_plain_flag_accepted(client):
    doc_a = _upload(client, _make_pdf_bytes(RENT_LINES), "rent.pdf")
    doc_b = _upload(client, _make_pdf_bytes(RIGHTS_LINES), "rights.pdf")
    payload = {
        "question": "When is rent due?",
        "doc_id_a": doc_a["doc_id"],
        "doc_id_b": doc_b["doc_id"],
        "plain_language": True,
    }
    resp = client.post("/compare", json=payload)
    assert resp.status_code == 200
    assert "plain language" in resp.json()["side_a"]["answer"].lower()


def test_action_plan_returns_checklist_and_draft(client):
    doc = _upload(client, _make_pdf_bytes(RENT_LINES))
    resp = client.post(
        "/action-plan",
        json={"topic": "Late-fee dispute for March", "doc_ids": [doc["doc_id"]]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["checklist"]) >= 3
    assert any("lawyer" in s.lower() for s in body["checklist"])
    assert body["draft"].startswith("[DRAFT")
    assert "not legal advice" in body["disclaimer"].lower()


def test_ask_rejects_short_question(client):
    resp = client.post("/ask", json={"question": "hi"})
    assert resp.status_code == 422


def test_action_plan_rejects_short_topic(client):
    resp = client.post("/action-plan", json={"topic": "hi"})
    assert resp.status_code == 422
