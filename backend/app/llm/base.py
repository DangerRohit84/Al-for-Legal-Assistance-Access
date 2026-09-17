"""LLM port (DIP): high-level code depends on this abstraction, not vendors."""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def answer(self, question: str, context: list, plain_language: bool = False) -> str:
        """Return a grounded draft answer given retrieved context chunks."""
