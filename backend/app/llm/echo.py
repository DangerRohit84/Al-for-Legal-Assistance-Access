"""Offline deterministic provider: keeps MVP + tests working without keys.

DIP implementation of LLMProvider (deterministic, zero-network). Extractive
baseline: leads with the top-ranked chunk plus page+clause citations so the
demo/video stays stable offline. Plain-language mode prefixes an everyday-
language rewrite marker with identical citations (same evidence, simpler
framing). Generative upgrades (gemini/openai-compat) reuse the same grounded
prompt + hard Cannot Determine override, so switching providers never weakens
trust guarantees.
"""
from __future__ import annotations

from ..prompting import CANNOT_DETERMINE, format_citations
from .base import LLMProvider


class EchoGroundedProvider(LLMProvider):
    """Deterministic extractive baseline (offline default for demo/tests)."""

    name = "echo"

    def answer(self, question: str, context: list, plain_language: bool = False) -> str:
        """Return extractive grounded draft with citations, or refusal."""
        if not context:
            return CANNOT_DETERMINE
        cites = format_citations(context)
        lead = context[0].text[:400].strip()
        if plain_language:
            # Intentional style switch: same evidence, plain framing.
            # Visible prefix lets the UI toggle demonstrate the difference
            # deterministically without a network LLM call.
            return f"In plain language: {lead} {cites}"
        return f"Based on the provided documents: {lead} {cites}"
