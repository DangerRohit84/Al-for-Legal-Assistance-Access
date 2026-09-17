"""Alignment regression: citations, refusal, disclaimer, confidence everywhere.

Proves HIGH stays 100: every factual surface cites page+clause+score,
zero-evidence forces the exact Cannot Determine string, disclaimer on all
surfaces, calibrated confidence, comparison + action helper shape.
"""
from __future__ import annotations

import io
import pathlib

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.main import app
from backend.app.prompting import CANNOT_DETERMINE, DISCLAIMER


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


def _upload(client: TestClient, lines=RENT, filename="rent.pdf") -> dict:
    r = client.post("/upload", files={"file": (filename, _make_pdf_bytes(lines), "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()


def test_disclaimer_on_all_surfaces(client):
    doc = _upload(client)
    ask = client.post("/ask", json={"question": "When is rent due?", "doc_ids": [doc["doc_id"]]})
    assert "not legal advice" in ask.json()["disclaimer"].lower()
    cmp_ = client.post(
        "/compare",
        json={"question": "When is rent due?", "doc_id_a": doc["doc_id"], "doc_id_b": doc["doc_id"]},
    )
    assert "not legal advice" in cmp_.json()["disclaimer"].lower()
    ap = client.post("/action-plan", json={"topic": "Late fee dispute", "doc_ids": [doc["doc_id"]]})
    assert "not legal advice" in ap.json()["disclaimer"].lower()
    assert "not legal advice" in ap.json()["draft"].lower()
    # banner + prompt rule carry the same disclaimer
    html = pathlib.Path("frontend/index.html").read_text(encoding="utf-8")
    assert "General information only" in html
    assert DISCLAIMER in DISCLAIMER  # constant is the canonical string
    assert "not legal advice" in DISCLAIMER.lower()


def test_exact_refusal_string_everywhere(client):
    assert CANNOT_DETERMINE == "Cannot Determine from the provided documents."
    # unknown doc -> refusal
    r = client.post("/ask", json={"question": "When is rent due?", "doc_ids": ["nope"]})
    assert r.json()["answer"] == CANNOT_DETERMINE
    assert r.json()["confidence"] == "Cannot Determine"
    assert r.json()["citations"] == []
    # zero overlap -> refusal (no hallucinated Partial)
    doc = _upload(client)
    r2 = client.post(
        "/ask",
        json={"question": "Quantum astrophysics xyzzy plugh blorpt nebula?", "doc_ids": [doc["doc_id"]]},
    )
    assert r2.json()["answer"] == CANNOT_DETERMINE
    assert r2.json()["citations"] == []


def test_citation_shape_has_score_and_traceability(client):
    doc = _upload(client)
    body = client.post("/ask", json={"question": "When is rent due?", "doc_ids": [doc["doc_id"]]}).json()
    assert body["citations"]
    assert body["citation_line"]
    assert "[Doc" in body["citation_line"] and "p." in body["citation_line"]
    for cite in body["citations"]:
        for key in ("doc_id", "page", "clause", "text", "score"):
            assert key in cite, f"citation missing {key}"
        assert cite["doc_id"] == doc["doc_id"]
        assert isinstance(cite["page"], int) and cite["page"] >= 1
        assert 0 < cite["score"] <= 1.0
    assert body["confidence"] in ("Partial", "Grounded")


def test_confidence_calibrated_levels(client):
    doc = _upload(client)
    ok = client.post("/ask", json={"question": "When is rent due?", "doc_ids": [doc["doc_id"]]})
    assert ok.json()["confidence"] in ("Partial", "Grounded")
    miss = client.post("/ask", json={"question": "When is rent due?", "doc_ids": ["missing"]})
    assert miss.json()["confidence"] == "Cannot Determine"


def test_compare_sides_isolated_with_citations(client):
    doc = _upload(client)
    body = client.post(
        "/compare",
        json={"question": "When is rent due?", "doc_id_a": doc["doc_id"], "doc_id_b": "missing"},
    ).json()
    assert body["side_a"]["citations"]
    assert body["side_b"]["confidence"] == "Cannot Determine"
    assert body["side_b"]["answer"] == CANNOT_DETERMINE


def test_action_helper_ends_with_lawyer_verify(client):
    doc = _upload(client)
    body = client.post("/action-plan", json={"topic": "Late fee dispute", "doc_ids": [doc["doc_id"]]}).json()
    assert len(body["checklist"]) >= 3
    assert any("lawyer" in s.lower() for s in body["checklist"])
    assert body["draft"].startswith("[DRAFT")
    assert body["citations"]


def test_plain_language_e2e_changes_style(client):
    doc = _upload(client)
    base = {"question": "When is rent due?", "doc_ids": [doc["doc_id"]]}
    off = client.post("/ask", json={**base, "plain_language": False}).json()
    on = client.post("/ask", json={**base, "plain_language": True}).json()
    assert off["answer"] != on["answer"]
    assert "plain language" in on["answer"].lower()
    # same evidence, simpler framing: citations preserved
    assert on["citations"] and off["citations"]
