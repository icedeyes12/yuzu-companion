from __future__ import annotations

import logging
from app.providers.base import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class CerebrasProvider(OpenAICompatibleProvider):
    """Cerebras AI provider via OpenAI-compatible API."""

    AVAILABLE_MODELS = [
        "qwen-3-235b-a22b-instruct-2507",
        "qwen-3-235b-a22b-thinking-2507",
        "qwen-3-coder-480b",
        "qwen-3-32b",
        "gpt-oss-120b",
        "llama-3.3-70b",
        "llama-4-scout-17b-16e-instruct",
        "llama3.1-8b",
    ]

    def __init__(self, config: dict | None = None):
        super().__init__(
            "cerebras",
            config,
            base_url="https://api.cerebras.ai/v1",
        )

    async def get_models(self) -> list[str]:
        """Return hardcoded model list."""
        return list(self.AVAILABLE_MODELS)
