from __future__ import annotations


import logging
from typing import AsyncGenerator
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from app.providers.base import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter provider via OpenAI-compatible API.

    Adds custom headers (HTTP-Referer, X-Title) and extra_body
    for OpenRouter-specific routing.
    """

    AVAILABLE_MODELS = [
        "deepseek/deepseek-chat-v3-0324:free",
        "deepseek/deepseek-v4-flash:free",
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "anthropic/claude-sonnet-4",
        "google/gemini-2.5-flash",
        "qwen/qwen3-235b-a22b",
        "deepseek/deepseek-chat-v3.1:free",
        "deepseek/deepseek-r1:free",
        "google/gemini-flash-1.5-8b:free",
        "google/gemini-flash-1.5:free",
        "meituan/longcat-flash-chat:free",
        "openai/gpt-4o-mini:free",
        "openai/gpt-4o-mini-2024-07-18:free",
        "qwen/qwen3-235b-a22b:free",
        "qwen/qwen3-vl-235b-a22b-instruct:free",
        "tngtech/deepseek-r1-chimera:free",
        "tngtech/deepseek-r1t2-chimera:free",
        "z-ai/glm-4.5-air:free",
        "z-ai/glm-4.5-air-2507:free",
        "x-ai/grok-4.1-fast:free",
        "deepseek/deepseek-chat-v3-0324",
        "deepseek/deepseek-chat-v3.1",
        "deepseek/deepseek-v3.2",
        "deepseek/deepseek-v3.2-exp",
        "deepseek/deepseek-v3.2-speciale",
        "google/gemma-3-12b",
        "xiaomi/mimo-v2-flash",
        "minimax/minimax-m2",
        "moonshotai/kimi-k2.5",
        "moonshotai/kimi-k2-0905",
        "openai/gpt-oss-120b",
        "qwen/qwen3-235b-a22b-2507",
        "qwen/qwen3-coder",
        "qwen/qwen3.5-397b-a17b",
        "qwen/qwen3.5-plus-02-15",
        "tngtech/deepseek-r1t2-chimera",
        "z-ai/glm-4.6",
        "z-ai/glm-4.7",
        "openrouter/owl-alpha",
    ]

    def __init__(self, config: dict | None = None):
        super().__init__(
            "openrouter",
            config,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/icedeyes12/yuzu-companion",
                "X-Title": "Yuzu-Companion",
            },
        )

    async def get_models(self) -> list[str]:
        """Return hardcoded model list."""
        return list(self.AVAILABLE_MODELS)

    async def chat_complete(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ChatCompletion:
        """Override to inject OpenRouter-specific extra_body."""
        # Cap free-tier models
        if model.endswith(":free"):
            max_tokens = min(max_tokens or 2048, 2048)
            temperature = min(temperature, 0.8)

        kwargs.setdefault("extra_body", {})
        kwargs["extra_body"].setdefault("transforms", ["middle-out"])
        kwargs["extra_body"].setdefault("provider", {"sort": "throughput"})

        return await super().chat_complete(
            messages,
            model,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def chat_stream(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Override to inject OpenRouter-specific extra_body."""
        if model.endswith(":free"):
            max_tokens = min(max_tokens or 2048, 2048)
            temperature = min(temperature, 0.8)

        kwargs.setdefault("extra_body", {})
        kwargs["extra_body"].setdefault("transforms", ["middle-out"])
        kwargs["extra_body"].setdefault("provider", {"sort": "throughput"})

        async for chunk in super().chat_stream(
            messages,
            model,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ):
            yield chunk
