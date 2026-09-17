"""Offline deterministic provider: keeps MVP + tests working without keys."""
from __future__ import annotations

from ..prompting import CANNOT_DETERMINE, format_citations
from .base import LLMProvider


class EchoGroundedProvider(LLMProvider):
    name = "echo"

    def answer(self, question: str, context: list, plain_language: bool = False) -> str:
        if not context:
            return CANNOT_DETERMINE
        cites = format_citations(context)
        lead = context[0].text[:400].strip()
        if plain_language:
            # TODO(echo): replace prefix with real simplification once LLM-backed.
            # Visible plain-language rewrite so offline demo shows toggle difference.
            return f"In plain language: {lead} {cites}"
        return f"Based on the provided documents: {lead} {cites}"
