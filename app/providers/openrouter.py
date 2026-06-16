from __future__ import annotations

# FILE: app/providers/openrouter.py
# DESCRIPTION: OpenRouter provider (https://openrouter.ai/api/v1)
#              Migrated to use the official openai SDK (AsyncOpenAI) via the
#              OpenAICompatibleProvider mixin in app/providers/openai_base.py.
#
# Phase C scope:
#   - HTTP/streaming moved from raw httpx/requests to AsyncOpenAI
#   - Hardcoded available_models list replaced with dynamic /v1/models fetch
#   - Custom HTTP-Referer and X-Title headers preserved (via _default_headers)
#   - OpenRouter-specific free-model clamps (max_tokens, temperature) preserved
#   - Vision message rewriting preserved
#   - parse_tool_calls() preserved (consumed by orchestrator)
#   - 402/429 status mapping preserved (textual user-facing error)
#
# Migration caveat: OpenRouter exposes /api/v1/chat/completions, but
# client.models.list() lives at /api/v1/models. We point the SDK at
# /api/v1 (no /chat/completions suffix) so the helper can hit both.

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from app.providers.base import AIProvider
from app.providers.openai_base import OpenAICompatibleProvider
from app.tools import multimodal_tools

logger = logging.getLogger(__name__)


# A small static set of "preferred" models we know work well for OpenRouter.
# The live model catalogue comes from /v1/models; this is just a fallback
# that keeps the provider usable if the live fetch is transiently down.
_PREFERRED_OPENROUTER_MODELS: list[str] = [
    "anthropic/claude-sonnet-4",
    "openai/gpt-4o",
    "google/gemini-2.5-flash",
    "qwen/qwen3-235b-a22b-2507",
    "minimax/minimax-m2",
]


class OpenRouterProvider(OpenAICompatibleProvider, AIProvider):
    def __init__(self, config: dict | None = None):
        super().__init__("openrouter", config)
        # SDK base URL: strip the trailing /chat/completions so client.models.list()
        # resolves to /api/v1/models.
        self.base_url = "https://openrouter.ai/api/v1"
        # Custom headers that must ride on every request. The mixin's
        # _build_client() reads _default_headers and passes it as
        # default_headers= to AsyncOpenAI.
        self._default_headers: dict[str, str] = {
            "HTTP-Referer": "https://github.com/icedeyes12/yuzu-companion",
            "X-Title": "Yuzu-Companion",
        }
        # Cached model list fetched lazily from /v1/models
        self._remote_models: list[str] = []
        self._remote_models_fetched_at: float = 0.0
        self._remote_models_ttl: float = 300.0

    # ── Model catalogue (dynamic) ──────────────────────────────────────

    async def _refresh_remote_models(self, force: bool = False) -> list[str]:
        now = time.time()
        if (
            not force
            and self._remote_models
            and (now - self._remote_models_fetched_at) < self._remote_models_ttl
        ):
            return self._remote_models
        try:
            ids = await self.fetch_remote_models()
        except Exception as e:  # noqa: BLE001
            logger.warning("[openrouter] /v1/models refresh failed: %s", e)
            return self._remote_models
        if ids:
            self._remote_models = sorted(set(ids))
            self._remote_models_fetched_at = now
        return self._remote_models

    async def get_models(self) -> list[str]:
        """Return the current best-known OpenRouter model list.

        Strategy: cached remote list (refreshed every 5 min), with the
        small _PREFERRED_OPENROUTER_MODELS whitelist hoisted to the top.
        """
        remote = await self._refresh_remote_models()
        if not remote:
            return list(_PREFERRED_OPENROUTER_MODELS)
        preferred_present = [m for m in _PREFERRED_OPENROUTER_MODELS if m in remote]
        preferred_only = [m for m in _PREFERRED_OPENROUTER_MODELS if m not in remote]
        return preferred_present + remote + preferred_only

    # ── Message prep (vision + free-model clamps) ──────────────────────

    def _prepare_messages_and_kwargs(
        self, messages: list[dict], model: str, stream: bool, **kwargs
    ) -> tuple[list[dict], dict]:
        messages = self._normalize_messages(messages)

        if self.supports_vision(model) and messages:
            last_user_message = self._get_last_user_message(messages)
            if last_user_message and multimodal_tools.has_images(last_user_message):
                vision_messages = self.format_vision_message(last_user_message)
                messages = self._replace_last_user_message(
                    messages, last_user_message, vision_messages
                )

        temperature = kwargs.get("temperature", 0.73)
        max_tokens = kwargs.get("max_tokens")
        top_p = kwargs.get("top_p", 0.9)
        top_k = kwargs.get("top_k", 40)
        typical_p = kwargs.get("typical_p", 0.8)

        if model.endswith(":free"):
            max_tokens = min(max_tokens or 2048, 2048)
            temperature = min(temperature, 0.8)

        extra: dict = {}
        if top_k is not None:
            extra["top_k"] = top_k
        if typical_p is not None:
            extra["typical_p"] = typical_p

        tools = kwargs.get("tools")
        if tools:
            extra["tools"] = tools
            if not stream:
                extra["tool_choice"] = "auto"

        return messages, {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "extra": extra,
        }

    # ── Public send_message (text) ─────────────────────────────────────

    async def send_message(
        self, messages: list[dict], model: str, **kwargs
    ) -> str | None:
        if not self.api_key:
            return None
        self._last_source = kwargs.get("source", "llm")
        try:
            messages, params = self._prepare_messages_and_kwargs(
                messages, model, False, **kwargs
            )
            logger.debug(
                f"[OpenRouter] {model} | max_tokens={params['max_tokens'] or 'unlimited'}"
            )
            raw = await self._chat_complete(
                model,
                messages,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
                top_p=params["top_p"],
                extra=params["extra"],
            )
            self._last_raw_response = raw
            message = raw["choices"][0]["message"]
            content = message.get("content", "")
            return content.strip() if content else ""
        except Exception as e:  # noqa: BLE001
            # Map known HTTP statuses to user-facing strings (preserve legacy contract)
            status = getattr(e, "status_code", None)
            if status == 402:
                return (
                    "OpenRouter free tier limit reached. Please try a different "
                    "model or add credits."
                )
            if status == 429:
                return "Rate limit exceeded. Please wait a moment and try again."
            logger.debug(f"[OpenRouter] send_message error: {e}")
            return None

    # ── Public send_message_raw (full response dict) ───────────────────

    async def send_message_raw(
        self, messages: list[dict], model: str, **kwargs
    ) -> dict | None:
        if not self.api_key:
            return None
        self._last_source = kwargs.get("source", "llm")
        try:
            messages, params = self._prepare_messages_and_kwargs(
                messages, model, False, **kwargs
            )
            raw = await self._chat_complete(
                model,
                messages,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
                top_p=params["top_p"],
                extra=params["extra"],
            )
            self._last_raw_response = raw
            return raw
        except Exception as e:  # noqa: BLE001
            status = getattr(e, "status_code", None)
            body = ""
            try:
                body = e.response.text[:500]  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass
            logger.warning(
                f"[OpenRouter] raw error {status}: {body}"
                if status
                else f"[OpenRouter] raw error: {e}"
            )
            return None

    # ── Streaming ──────────────────────────────────────────────────────

    async def send_message_streaming(
        self, messages: list[dict], model: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            yield ""
            return
        self._last_source = kwargs.get("source", "llm")
        try:
            messages, params = self._prepare_messages_and_kwargs(
                messages, model, True, **kwargs
            )
            async for chunk in self._chat_stream(
                model,
                messages,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
                top_p=params["top_p"],
                extra=params["extra"],
            ):
                yield chunk
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            yield f"Error: {str(e)}"

    # ── Tool-call parsing (consumed by orchestrator) ───────────────────

    def parse_tool_calls(self, raw_response) -> list[dict]:
        """Parse tool_calls from a raw OpenAI-compatible response.

        Preserved verbatim from the previous implementation because the
        orchestrator's _parse_raw_tool_calls_async() relies on the exact
        {"id","name","arguments"} shape.
        """
        if not isinstance(raw_response, dict):
            return []
        try:
            message = raw_response.get("choices", [{}])[0].get("message", {})
            tool_calls = message.get("tool_calls", [])
            results = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                results.append(
                    {
                        "id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "arguments": json.loads(fn.get("arguments", "{}")),
                    }
                )
            return results
        except Exception:  # noqa: BLE001
            return []
