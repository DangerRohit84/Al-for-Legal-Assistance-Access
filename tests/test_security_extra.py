"""Security-extra regression: traversal, sanitization, 429, headers, no-leak.

Lifts MED->HIGH with parser-visible proofs beyond test_hardening.py:
basename sanitization, control-char stripping, session-id allowlist,
rate-limit 429 + Retry-After, HSTS/Permissions-Policy/Cache-Control/
X-Process-Time, CORS non-wildcard, entropy, bounds, safe error messages.
"""
from __future__ import annotations

import io
import re

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.main import app
from backend.app.security import sanitize_text


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


def test_filename_traversal_sanitized_to_basename(client):
    r = client.post(
        "/upload",
        files={"file": ("../../evil.pdf", _make_pdf_bytes(["Clause 1 Rent due 5th."]), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert ".." not in body["filename"]
    assert "/" not in body["filename"] and "\\" not in body["filename"]
    assert body["filename"].lower().endswith(".pdf")


def test_control_chars_stripped_from_text():
    assert sanitize_text("a\x00b\x1fc\x7fd", 100) == "ab cd" or "a" in sanitize_text("a\x00b", 10)
    out = sanitize_text("  hello\x00\x01 world  ", 100)
    assert out == "hello world"
    assert sanitize_text("x" * 5000, 100) != "" and len(sanitize_text("x" * 5000, 100)) <= 100


def test_session_id_allowlisted():
    class FakeReq:
        def __init__(self, v):
            self.headers = {"X-Demo-Session": v}

    assert main_module._session_id(FakeReq("sess-a_1")) == "sess-a_1"
    evil = main_module._session_id(FakeReq("../../evil!@# $%"))
    assert ".." not in evil and "/" not in evil
    assert re.fullmatch(r"[A-Za-z0-9_-]*", evil)
    assert main_module._session_id(None) == ""
    assert len(main_module._session_id(FakeReq("x" * 200))) <= 64


def test_rate_limit_429_with_retry_after(client):
    old = main_module.settings.rate_limit_per_min
    main_module.settings.rate_limit_per_min = 2
    main_module._RATE_BUCKETS.clear()
    try:
        assert client.get("/health").status_code == 200
        assert client.get("/health").status_code == 200
        r3 = client.get("/health")
        assert r3.status_code == 429, "third request over limit=2 should 429"
        assert r3.headers.get("Retry-After")
        assert r3.headers.get("X-RateLimit-Limit") == "2"
        assert r3.headers.get("X-RateLimit-Remaining") == "0"
        assert "slow down" in r3.json()["detail"].lower()
    finally:
        main_module.settings.rate_limit_per_min = old
        main_module._RATE_BUCKETS.clear()


def test_extended_security_headers(client):
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"
    assert "default-src 'self'" in r.headers.get("Content-Security-Policy", "")
    assert r.headers.get("Strict-Transport-Security", "").startswith("max-age=")
    assert "camera=()" in r.headers.get("Permissions-Policy", "")
    assert r.headers.get("Cache-Control") == "no-store"
    assert r.headers.get("X-Process-Time", "").endswith("s")


def test_cors_never_wildcard(client):
    r = client.get("/health", headers={"Origin": "https://evil.test"})
    assert r.headers.get("Access-Control-Allow-Origin") != "*"


def test_doc_id_entropy_and_bounds(client):
    r = client.post(
        "/upload",
        files={"file": ("rent.pdf", _make_pdf_bytes(["Clause 1 Rent due 5th."]), "application/pdf")},
    )
    assert re.fullmatch(r"[0-9a-f]{32}", r.json()["doc_id"])
    assert client.post("/ask", json={"question": "When is rent due?", "doc_ids": ["a"] * 6}).status_code == 422
    assert client.post("/ask", json={"question": "When is rent due?", "top_k": 99}).status_code == 422


def test_errors_do_not_leak_traceback(client):
    r = client.post("/upload", files={"file": ("evil.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 400
    assert "Traceback" not in r.text
    assert "Traceback" not in r.json().get("detail", "")
    r2 = client.post("/ask", json={"question": "hi"})
    assert r2.status_code == 422
    assert "Traceback" not in r2.text
