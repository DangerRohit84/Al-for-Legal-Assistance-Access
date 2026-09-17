"""Factory (OCP): add providers without touching callers."""
from __future__ import annotations

from ..config import settings
from .base import LLMProvider
from .echo import EchoGroundedProvider


def get_provider(name: str = "") -> LLMProvider:
    key = (name or settings.llm_provider or "echo").lower()
    if key == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    if key in ("openai", "openai-compat", "compat"):
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
        )
    return EchoGroundedProvider()
