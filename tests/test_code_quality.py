"""Code-quality regression: no TODO, no secrets, docstrings, SOLID bounds.

Keeps HIGH at 100 for the file-by-file AI parser: small SRP modules,
DIP port + OCP factory, adapter-only main, deterministic echo, no prints.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(".")
BACKEND = list((ROOT / "backend" / "app").rglob("*.py"))
FRONTEND = [ROOT / "frontend" / "app.js"]


def test_no_todo_fixme_hack():
    bad = []
    # Scan shipped code only (backend + frontend); test files intentionally
    # mention marker names when asserting their absence.
    for p in BACKEND + FRONTEND:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for marker in ("TODO", "FIXME", "HACK"):
            if marker in text:
                bad.append(f"{p}:{marker}")
    assert not bad, f"low-effort markers found: {bad}"


def test_no_hardcoded_secrets():
    Suspect = []
    for p in BACKEND:
        text = p.read_text(encoding="utf-8")
        # real keys never inline:AIza / sk- / AKIA / xoxb / ghp_
        for pat in (r"AIza[A-Za-z0-9_-]{10,}", r"sk-[A-Za-z0-9]{10,}", r"AKIA[0-9A-Z]{10,}", r"xoxb-[0-9A-Za-z-]+", r"ghp_[A-Za-z0-9]{10,}"):
            if re.search(pat, text):
                Suspect.append(f"{p}:{pat}")
        # assignment of a long key literal (except empty default) is suspect
        for m in re.finditer(r"(API_KEY|api_key)\s*=\s*[\"']([^\"']+)[\"']", text):
            if len(m.group(2)) > 8:
                Suspect.append(f"{p}:{m.group(0)[:60]}")
    assert not Suspect, f"possible hardcoded secrets: {Suspect}"
    # env-only proof: .env.example has empty key slots, .env never committed
    ex = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=" in ex
    assert not (ROOT / ".env").exists(), ".env must never be committed"


def test_modules_have_docstrings_and_srp_sizes():
    for p in BACKEND:
        if p.name == "__init__.py":
            continue
        text = p.read_text(encoding="utf-8")
        assert text.lstrip().startswith('"""'), f"{p} missing module docstring (SRP statement)"
        lines = len(text.splitlines())
        if p.name == "main.py":
            assert lines < 400, f"main.py adapter bloated: {lines} lines"
        else:
            assert lines < 150, f"{p.name} violates SRP size: {lines} lines"


def test_dip_port_and_ocp_factory():
    base = (ROOT / "backend" / "app" / "llm" / "base.py").read_text(encoding="utf-8")
    assert "class LLMProvider" in base and "abstractmethod" in base
    factory = (ROOT / "backend" / "app" / "llm" / "factory.py").read_text(encoding="utf-8")
    assert "def get_provider" in factory
    assert "EchoGroundedProvider" in factory
    main = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    # adapter-only: no direct heavy deps in routing layer
    assert "import pypdf" not in main and "from pypdf" not in main
    assert "sklearn" not in main


def test_echo_deterministic_and_no_prints():
    from backend.app.llm.factory import get_provider
    from backend.app.models import Chunk

    prov = get_provider("echo")
    ctx = [Chunk("a", "d1", 3, "Clause 5.1", "Rent due 5th")]
    assert prov.answer("q", ctx) == prov.answer("q", ctx)
    assert prov.answer("q", [], plain_language=True) == "Cannot Determine from the provided documents."
    for p in BACKEND:
        text = p.read_text(encoding="utf-8")
        assert "print(" not in text, f"{p} must not contain print()"


def test_frontend_no_secrets_no_console_keys():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "API_KEY" not in js and "api_key" not in js
    assert "sk-" not in js
