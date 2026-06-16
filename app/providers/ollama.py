from __future__ import annotations

import logging
import httpx
from app.providers.base import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class OllamaProvider(OpenAICompatibleProvider):
    """Ollama provider via OpenAI-compatible /v1/ endpoint.

    Ollama exposes an OpenAI-compatible API at /v1/ since v0.1.24.
    We use that instead of the native /api/chat endpoint.
    """

    AVAILABLE_MODELS = [
        "smollm:360m",
        "smollm2:360m",
        "glm-4.6:cloud",
        "qwen3-vl:235b-cloud",
        "qwen3-coder:480b-cloud",
        "kimi-k2:1t-cloud",
        "kimi-k2.5:cloud",
        "gpt-oss:120b-cloud",
        "gpt-oss:20b-cloud",
        "deepseek-v3.1:671b-cloud",
    ]

    def __init__(self, config: dict | None = None):
        ollama_base = (config or {}).get("base_url", "http://127.0.0.1:11434")
        super().__init__(
            "ollama",
            config,
            base_url=f"{ollama_base.rstrip('/')}/v1",
        )
        self._ollama_base = ollama_base

    async def get_models(self) -> list[str]:
        """Fetch models from Ollama's native /api/tags endpoint.

        Falls back to hardcoded list if Ollama is unreachable.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._ollama_base}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    if models:
                        return sorted(models)
        except Exception as e:
            logger.debug("[Ollama] Failed to fetch models: %s", e)
        return list(self.AVAILABLE_MODELS)

    async def test_connection(self) -> bool:
        """Test connection via Ollama's native API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._ollama_base}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
