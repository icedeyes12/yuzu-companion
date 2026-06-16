from __future__ import annotations

# FILE: app/providers/openai_base.py
# DESCRIPTION: Mixin providing a shared AsyncOpenAI client and common helpers
#              for OpenAI-compatible providers (Chutes, OpenRouter, Cerebras, Ollama).
#
# Migration strategy:
#   - Each provider that talks to an OpenAI-compatible endpoint inherits from
#     OpenAICompatibleProvider in addition to AIProvider.
#   - The mixin owns one AsyncOpenAI client per (provider, api_key) — keyed by
#     (provider_name, api_key) so that key rotation produces a new client.
#   - All HTTP/socket-level concerns (httpx, requests, aiter_lines) are
#     delegated to the official SDK. Providers do not construct their own
#     clients anymore.
#
# Behavior MUST remain equivalent to the existing implementation:
#   - Rate limiting (per-provider, per-model) still applies via _rate_limit_provider
#   - 429 retries with exponential backoff still apply
#   - Vision message rewriting still happens in providers (multimodal)
#   - Cancellation propagates cleanly (AsyncOpenAI accepts an httpx client whose
#     timeouts can be cancelled mid-stream)

import logging
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI

from app.providers.rate_limit import _rate_limit_provider

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    """Mixin that gives a provider an ``AsyncOpenAI`` client.

    Concrete providers must initialize ``self.base_url`` and call
    ``self._ensure_client()`` before any SDK call. The client is rebuilt
    whenever the API key changes so key rotation Just Works.
    """

    #: Override in subclass. e.g. "https://llm.chutes.ai/v1"
    base_url: str = ""

    #: Per-provider SDK client, lazily built
    _client: AsyncOpenAI | None = None
    _client_key: tuple[str, str | None] | None = None

    def _build_client(self) -> AsyncOpenAI:
        """Build a fresh AsyncOpenAI client for this provider.

        Subclasses may override to add custom headers (e.g. OpenRouter's
        ``HTTP-Referer`` / ``X-Title``) by setting ``self._default_headers``
        before calling ``super()._build_client()`` or by extending
        ``self._client_kwargs`` instead.
        """
        kwargs: dict[str, Any] = {
            "api_key": self.api_key or "no-key",
            "base_url": self.base_url,
            "max_retries": 0,  # we handle 429/backoff at the rate-limit layer
            "timeout": 120.0,
        }
        extra_headers = getattr(self, "_default_headers", None)
        if extra_headers:
            kwargs["default_headers"] = extra_headers
        return AsyncOpenAI(**kwargs)

    def _ensure_client(self) -> AsyncOpenAI:
        """Return the cached client, rebuilding it if the key changed."""
        key = (self.name, self.api_key)
        if self._client is None or self._client_key != key:
            self._client = self._build_client()
            self._client_key = key
        return self._client

    def invalidate_client(self) -> None:
        """Drop the cached client (e.g. after a key reload)."""
        self._client = None
        self._client_key = None

    # ── Common SDK helpers ──────────────────────────────────────────────

    async def fetch_remote_models(self) -> list[str]:
        """Fetch the model list from the provider's ``/v1/models`` endpoint.

        Returns an empty list on failure (e.g. no key, network error,
        provider doesn't expose a models endpoint). Concrete providers are
        expected to override ``get_models()`` to merge this list with any
        provider-specific static whitelist (e.g. vision-only models).
        """
        if not self.api_key:
            return []
        client = self._ensure_client()
        try:
            response = await client.models.list()
        except Exception as e:  # noqa: BLE001
            logger.warning("[%s] /v1/models fetch failed: %s", self.name, e)
            return []
        # OpenAI SDK returns Model objects with .id
        ids: list[str] = []
        for m in getattr(response, "data", []) or []:
            mid = getattr(m, "id", None)
            if isinstance(mid, str) and mid:
                ids.append(mid)
        return ids

    async def _chat_complete(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict:
        """One-shot (non-streaming) chat completion via the SDK.

        Wraps the call in the rate-limit context so existing 429/backoff
        semantics still apply. Returns the raw response dict.
        """
        client = self._ensure_client()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if top_p is not None:
            kwargs["top_p"] = top_p
        if tools:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
        if extra:
            kwargs.update(extra)

        source = getattr(self, "_last_source", "llm")
        async with _rate_limit_provider(self.name, model, source):
            response = await client.chat.completions.create(**kwargs)
        # Serialize to a plain dict so callers can introspect.
        # Pydantic v2 models support .model_dump()
        if hasattr(response, "model_dump"):
            return response.model_dump()
        return response  # type: ignore[return-value]

    async def _chat_stream(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completion via the SDK.

        Yields content deltas (string) only. Providers can layer additional
        metadata (e.g. tool_call deltas) on top if needed.
        """
        client = self._ensure_client()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if top_p is not None:
            kwargs["top_p"] = top_p
        if tools:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
        if extra:
            kwargs.update(extra)

        source = getattr(self, "_last_source", "llm")
        async with _rate_limit_provider(self.name, model, source):
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    yield content


__all__ = ["OpenAICompatibleProvider"]
