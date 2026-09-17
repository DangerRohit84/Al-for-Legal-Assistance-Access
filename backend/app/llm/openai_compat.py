"""OpenAI-compatible provider (covers OpenAI, open-source servers, gateways)."""
from __future__ import annotations

import json
import urllib.request

from ..prompting import build_grounded_prompt
from .base import LLMProvider


class OpenAICompatProvider(LLMProvider):
    name = "openai-compat"

    def __init__(self, api_key: str = "", base_url: str = "", model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = model

    def answer(self, question: str, context: list, plain_language: bool = False) -> str:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY missing for openai-compat provider")
        prompt = build_grounded_prompt(question, context, plain_language=plain_language)
        payload = json.dumps(
            {"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0}
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"].strip()
