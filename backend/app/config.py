"""Env-driven settings. No secrets in code. All LLM keys via environment."""
import os


def _origins(raw: str) -> list:
    return [o.strip() for o in (raw or "").split(",") if o.strip()]


class Settings:
    """Single-responsibility: read env, expose typed knobs."""

    def __init__(self) -> None:
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "echo").lower()
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.max_chunks: int = int(os.getenv("MAX_CHUNKS", "5"))
        self.port: int = int(os.getenv("PORT", "8000"))
        # Security knobs: same-origin by default (no CORS wildcard).
        # Set FRONTEND_ORIGIN=https://your-app.run.app for cross-origin prod.
        self.frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "")
        self.allowed_origins: list = _origins(os.getenv("ALLOWED_ORIGINS", self.frontend_origin))
        self.max_doc_ids: int = int(os.getenv("MAX_DOC_IDS", "5"))
        self.max_store_chunks: int = int(os.getenv("MAX_STORE_CHUNKS", "5000"))
        self.demo_mode: str = os.getenv("DEMO_MODE", "true").lower()


settings = Settings()
