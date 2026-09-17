"""Optional Gemini provider (Google touchpoint). Lazy import so base install stays light."""
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
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as exc:
            raise ValueError("google-generativeai not installed: pip install google-generativeai") from exc
        genai.configure(api_key=self.api_key)
        prompt = build_grounded_prompt(question, context, plain_language=plain_language)
        resp = genai.GenerativeModel(self.model).generate_content(prompt)
        return (getattr(resp, "text", "") or "").strip()
