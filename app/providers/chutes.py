from __future__ import annotations

import logging
from app.providers.base import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class ChutesProvider(OpenAICompatibleProvider):
    """Chutes AI provider via OpenAI-compatible API."""

    # Hardcoded model list — Chutes /v1/models may not be reliable
    AVAILABLE_MODELS = [
        "google/gemma-4-31B-turbo-TEE",
        "Qwen/Qwen3.6-27B-TEE",
        "Qwen/Qwen3.5-397B-A17B-TEE",
        "Qwen/Qwen3-32B-TEE",
        "Qwen/Qwen3-235B-A22B-Thinking-2507",
        "deepseek-ai/DeepSeek-V3.2-TEE",
        "MiniMaxAI/MiniMax-M2.5-TEE",
        "moonshotai/Kimi-K2.5-TEE",
        "moonshotai/Kimi-K2.6-TEE",
        "Nemotron-3-Nano-Omni-30B-TEE",
        "Qwen/Qwen2.5-Coder-32B-Instruct-TEE",
        "unsloth/Mistral-Nemo-Instruct-2407-TEE",
        "zai-org/GLM-5-TEE",
        "zai-org/GLM-5.1-TEE",
    ]

    def __init__(self, config: dict | None = None):
        super().__init__(
            "chutes",
            config,
            base_url="https://llm.chutes.ai/v1",
        )
        self._last_error: str | None = None

    async def get_models(self) -> list[str]:
        """Return hardcoded model list (Chutes /v1/models is unreliable)."""
        return list(self.AVAILABLE_MODELS)
