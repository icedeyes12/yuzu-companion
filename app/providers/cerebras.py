from __future__ import annotations

# FILE: app/providers/cerebras.py
# DESCRIPTION: Cerebras provider (https://api.cerebras.ai/v1)
#              Migrated to use the official openai SDK (AsyncOpenAI) via the
#              OpenAICompatibleProvider mixin in app/providers/openai_base.py.
#
# Phase C scope:
#   - HTTP/streaming moved from raw httpx/requests to AsyncOpenAI
#   - Hardcoded available_models list replaced with dynamic /v1/models fetch
#   - Top-k and typical-p passthrough preserved via extra=
#   - sync send_message preserved as async (matches AIProvider contract)
#   - 120s default timeout preserved

import asyncio
import logging
import time
from typing import AsyncGenerator

from app.providers.base import AIProvider
from app.providers.openai_base import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


# A small static set of "preferred" models we know work well for Cerebras.
# The live model catalogue comes from /v1/models; this is just a fallback
# so the provider stays usable if the live fetch is transiently down.
_PREFERRED_CEREBRAS_MODELS: list[str] = [
    "qwen-3-235b-a22b-instruct-2507",
    "qwen-3-coder-480b",
    "llama-3.3-70b",
    "llama3.1-8b",
]


class CerebrasProvider(OpenAICompatibleProvider, AIProvider):
    def __init__(self, config: dict | None = None):
        super().__init__("cerebras", config)
        self.base_url = "https://api.cerebras.ai/v1"
        # Cached model list fetched lazily from /v1/models
        self._remote_models: list[str] = []
        self._remote_models_fetched_at: float = 0.0
        self._remote_models_ttl: float = 300.0
        # Default timeout for Cerebras calls (matches previous behaviour)
        self._default_timeout: float = 120.0

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
            logger.warning("[cerebras] /v1/models refresh failed: %s", e)
            return self._remote_models
        if ids:
            self._remote_models = sorted(set(ids))
            self._remote_models_fetched_at = now
        return self._remote_models

    async def get_models(self) -> list[str]:
        """Return the current best-known Cerebras model list.

        Strategy: cached remote list (refreshed every 5 min), with the
        small _PREFERRED_CEREBRAS_MODELS whitelist hoisted to the top.
        """
        remote = await self._refresh_remote_models()
        if not remote:
            return list(_PREFERRED_CEREBRAS_MODELS)
        preferred_present = [m for m in _PREFERRED_CEREBRAS_MODELS if m in remote]
        preferred_only = [m for m in _PREFERRED_CEREBRAS_MODELS if m not in remote]
        return preferred_present + remote + preferred_only

    # ── Shared param building ──────────────────────────────────────────

    def _build_params(
        self, model: str, messages: list[dict], stream: bool, **kwargs
    ) -> tuple[list[dict], dict, float]:
        messages = self._normalize_messages(messages)
        temperature = kwargs.get("temperature", 0.69)
        max_tokens = kwargs.get("max_tokens")
        top_p = kwargs.get("top_p", 0.7)
        top_k = kwargs.get("top_k", 40)
        typical_p = kwargs.get("typical_p", 0.8)
        timeout = float(kwargs.get("timeout", self._default_timeout))

        extra: dict = {}
        if top_k is not None:
            extra["top_k"] = top_k
        if typical_p is not None:
            extra["typical_p"] = typical_p

        return messages, {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "extra": extra,
        }, timeout

    # ── Public send_message (text) ─────────────────────────────────────

    async def send_message(
        self, messages: list[dict], model: str, **kwargs
    ) -> str | None:
        if not self.api_key:
            return None
        self._last_source = kwargs.get("source", "llm")
        try:
            messages, params, _timeout = self._build_params(
                model, messages, False, **kwargs
            )
            logger.debug(
                f"[Cerebras] {model} | new_msg=1 | max_tokens={params['max_tokens'] or 'unlimited'}"
            )
            raw = await self._chat_complete(
                model,
                messages,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
                top_p=params["top_p"],
                extra=params["extra"],
            )
            content = raw["choices"][0]["message"]["content"]
            return (content or "").strip()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[Cerebras] send_message error: {e}")
            return None

    # ── Public send_message_raw (full response dict) ───────────────────

    async def send_message_raw(
        self, messages: list[dict], model: str, **kwargs
    ) -> dict | None:
        if not self.api_key:
            return None
        self._last_source = kwargs.get("source", "llm")
        try:
            messages, params, _timeout = self._build_params(
                model, messages, False, **kwargs
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
            logger.debug(f"[Cerebras] send_message_raw error: {e}")
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
            messages, params, _timeout = self._build_params(
                model, messages, True, **kwargs
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
