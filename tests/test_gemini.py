"""Gemini provider migration: new google-genai SDK, no deprecation warning.

RED test for senior-dev migration from deprecated
`import google.generativeai` to `from google import genai` (google-genai).
Offline-safe: mocks Client, never hits network.
"""
from __future__ import annotations


def test_missing_key_raises():
    from backend.app.llm.gemini import GeminiProvider

    prov = GeminiProvider(api_key="")
    try:
        prov.answer("q?", [])
    except ValueError as exc:
        assert "GEMINI_API_KEY" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing key")


def test_missing_sdk_error_mentions_new_package():
    """Clear install hint must point to google-genai (not deprecated pkg)."""
    import builtins

    from backend.app.llm.gemini import GeminiProvider

    prov = GeminiProvider(api_key="test-key")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "google" or name.startswith("google.genai") or name.startswith("google.generativeai"):
            raise ImportError("No module named google")
        return real_import(name, *args, **kwargs)

    import unittest.mock as mock

    with mock.patch("builtins.__import__", side_effect=fake_import):
        try:
            prov.answer("q?", [])
        except ValueError as exc:
            assert "google-genai" in str(exc), f"error must mention google-genai, got: {exc}"
            assert "pip install google-genai" in str(exc)
        else:
            raise AssertionError("expected ValueError when SDK missing")


def test_new_sdk_called_with_temperature_zero():
    """New SDK path: Client(api_key) + generate_content(model, contents, temp 0)."""
    from unittest.mock import MagicMock, patch

    from backend.app.llm.gemini import GeminiProvider
    from backend.app.models import Chunk

    prov = GeminiProvider(api_key="test-key", model="gemini-2.0-flash")
    ctx = [Chunk("c1", "d1", 3, "Clause 5.1", "Rent due 5th")]

    fake_resp = MagicMock()
    fake_resp.text = "  Grounded answer [Doc d1 p.3, Clause 5.1]  "
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_resp

    with patch("google.genai.Client", return_value=fake_client):
        out = prov.answer("When is rent due?", ctx)

    assert out == "Grounded answer [Doc d1 p.3, Clause 5.1]"
    assert fake_client.models.generate_content.called, "must call new SDK generate_content"
    _, kwargs = fake_client.models.generate_content.call_args
    assert kwargs.get("model") == "gemini-2.0-flash"
    assert "contents" in kwargs
    # temperature 0 via GenerateContentConfig or dict
    cfg = kwargs.get("config")
    assert cfg is not None, "must pass temperature config"
    if isinstance(cfg, dict):
        assert cfg.get("temperature") == 0
    else:
        assert getattr(cfg, "temperature", None) == 0
    # prompt must be grounded (contains Rules + context delimiters)
    prompt = kwargs.get("contents", "")
    if isinstance(prompt, list):
        prompt = " ".join(str(p) for p in prompt)
    assert "Answer ONLY from the context" in prompt
    assert "<context>" in prompt


def test_no_deprecated_import_in_source():
    import pathlib

    src = pathlib.Path("backend/app/llm/gemini.py").read_text(encoding="utf-8")
    assert "google.generativeai" not in src or "google-genai" in src, (
        "must not use deprecated google.generativeai without fallback note"
    )
    # New SDK import must be present (lazy)
    assert "from google import genai" in src or "from google.genai" in src or "google.genai" in src
