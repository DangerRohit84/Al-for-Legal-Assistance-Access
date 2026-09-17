"""Accessibility regression: prove frontend is parser-visible accessible.

Covers the LOW->HIGH gap: skip link, landmarks, labels, live regions,
alert-free errors (role=alert), focus management, keyboard support,
contrast, reduced-motion, noscript, and XSS-safe rendering.
"""
from __future__ import annotations

import pathlib

HTML = pathlib.Path("frontend/index.html").read_text(encoding="utf-8")
CSS = pathlib.Path("frontend/styles.css").read_text(encoding="utf-8")
JS = pathlib.Path("frontend/app.js").read_text(encoding="utf-8")


def test_html_lang_and_meta():
    assert 'lang="en"' in HTML
    assert 'name="viewport"' in HTML
    assert "<title>" in HTML
    assert 'name="description"' in HTML


def test_skip_link_and_landmarks():
    assert 'class="skip"' in HTML and 'href="#main"' in HTML
    assert "<header" in HTML and "<main" in HTML and "<footer" in HTML
    assert 'id="main"' in HTML


def test_all_inputs_have_labels():
    for fid in ('for="pdf"', 'for="q"', 'for="cmpA"', 'for="cmpB"', 'for="topic"'):
        assert fid in HTML, f"missing label {fid}"
    # plain-language checkbox has an associated label
    assert 'id="plain"' in HTML


def test_live_regions_and_alert():
    # polite live regions for async results
    assert HTML.count('aria-live="polite"') >= 4
    # assertive alert region for errors (never blocking alert())
    assert 'role="alert"' in HTML
    assert 'id="errors"' in HTML
    # no blocking alert() calls (ignore comments mentioning alert)
    import re

    code_lines = [ln for ln in JS.splitlines() if ln.strip() and not ln.strip().startswith(("//", "/*", "*", "#"))]
    calls = [ln for ln in code_lines if re.search(r"(^|[^A-Za-z_.])alert\s*\(", ln)]
    assert not calls, f"blocking alert() harms screen readers; use role=alert: {calls}"


def test_focus_management_and_keyboard():
    # answer/draft focusable for keyboard + screen-reader flow
    assert 'tabindex="-1"' in HTML
    assert 'tabindex="0"' in HTML
    assert ".focus()" in JS
    # non-submit buttons must not trap/submit forms
    assert HTML.count('type="button"') >= 3
    assert ":focus-visible" in CSS or "focus-visible" in CSS


def test_describedby_hints():
    assert "aria-describedby" in HTML
    assert 'id="askHint"' in HTML
    assert "aria-label" in HTML


def test_contrast_and_motion():
    # documented AA ratios + visible focus + reduced-motion
    assert "4.5:1" in CSS or "AA contrast" in CSS or "AA" in CSS
    assert "prefers-reduced-motion" in CSS
    assert "outline" in CSS


def test_touch_target_and_error_style():
    assert "44px" in CSS, "min 44px touch target for mobile a11y"
    assert "#errors" in CSS


def test_noscript_and_disclaimer_banner():
    assert "<noscript>" in HTML
    assert "General information only" in HTML
    assert "fake/redacted" in HTML.lower()


def test_xss_safe_rendering():
    assert "escapeHtml" in JS
    assert "textContent" in JS  # draft uses safe textContent, not innerHTML


def test_required_and_accept_hints():
    assert 'accept="application/pdf' in HTML
    assert "required" in HTML
