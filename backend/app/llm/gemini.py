"""Optional Gemini provider (Google touchpoint). Lazy import so base install stays light.

Uses new ``google-genai`` SDK (``from google import genai``). Falls back to
deprecated ``google-generativeai`` only if new package is missing, for
backward compat during migration.
"""
from __future__ import annotations

from ..prompting import build_grounded_prompt
from .base import LLMProvider


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str = "", model: str = "gemini-2.0-flash") -> None:
        self.api_key = api_key
        self.model = model

    def answer(self, question: str, context: list, plain_language: bool = False) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY missing: set env to enable Gemini provider")
        prompt = build_grounded_prompt(question, context, plain_language=plain_language)
        # Preferred: new google-genai SDK (no deprecation warning).
        try:
            from google import genai as genai_new  # type: ignore
        except ImportError:
            genai_new = None  # type: ignore
        if genai_new is not None:
            try:
                from google.genai import types as genai_types  # type: ignore

                gen_config = genai_types.GenerateContentConfig(temperature=0)
            except Exception:
                # TypedDict fallback accepted by generate_content as config.
                gen_config = {"temperature": 0}  # type: ignore
            client = genai_new.Client(api_key=self.api_key)
            resp = client.models.generate_content(
                model=self.model, contents=prompt, config=gen_config
            )
            return (getattr(resp, "text", "") or "").strip()
        # Backward compat: old package if still installed.
        try:
            import google.generativeai as genai_legacy  # type: ignore
        except ImportError as exc:
            raise ValueError("google-genai not installed: pip install google-genai") from exc
        genai_legacy.configure(api_key=self.api_key)
        resp = genai_legacy.GenerativeModel(self.model).generate_content(prompt)
        return (getattr(resp, "text", "") or "").strip()
