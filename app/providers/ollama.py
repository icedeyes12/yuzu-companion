from __future__ import annotations

# FILE: app/providers/ollama.py
# DESCRIPTION: Local Ollama provider (default http://127.0.0.1:11434)
#              Migrated to use the official openai SDK (AsyncOpenAI) via the
#              OpenAICompatibleProvider mixin in app/providers/openai_base.py.
#
# Phase D scope:
#   - HTTP/streaming moved from raw httpx/requests to AsyncOpenAI
#   - Hardcoded available_models list replaced with dynamic /v1/models fetch
#   - Safe fallback to a small preferred list if /v1/models fails on older
#     Ollama versions (which historically did not expose OpenAI-compat
#     /v1/models)
#   - num_ctx (Ollama-specific option) preserved via extra=
#   - base_url configurable via self.config["base_url"], with /v1 suffix
#     appended for SDK compatibility
#   - Ollama is the only provider that does not need an API key

import asyncio
import logging
import time
from typing import AsyncGenerator

import httpx  # used only for the legacy /api/tags fallback when /v1/models fails
from app.providers.base import AIProvider
from app.providers.openai_base import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


# A small static set of "preferred" models we know work well for local
# Ollama. The live model catalogue normally comes from /v1/models, but
# we keep this as a last-ditch fallback if the server is unreachable.
_PREFERRED_OLLAMA_MODELS: list[str] = [
    "smollm:360m",
    "smollm2:360m",
    "glm-4.6:cloud",
    "qwen3-coder:480b-cloud",
    "gpt-oss:20b-cloud",
]


class OllamaProvider(OpenAICompatibleProvider, AIProvider):
    def __init__(self, config: dict | None = None):
        super().__init__("ollama", config)
        # Local Ollama HTTP root. The SDK needs the OpenAI-compat base, so
        # _sdk_base_url appends /v1 lazily.
        self.base_url_root = self.config.get(
            "base_url", "http://127.0.0.1:11434"
        ).rstrip("/")
        # Cached model list fetched lazily from /v1/models
        self._remote_models: list[str] = []
        self._remote_models_fetched_at: float = 0.0
        self._remote_models_ttl: float = 300.0
        # Default timeout for Ollama calls
        self._default_timeout: float = 180.0

    @property
    def base_url(self) -> str:
        """The SDK base URL (with /v1 suffix) for Ollama.

        AsyncOpenAI appends the endpoint paths itself, so this is the
        right shape for both ``chat.completions.create`` and
        ``models.list``.
        """
        return f"{self.base_url_root}/v1"

    @base_url.setter
    def base_url(self, value: str) -> None:
        # Allow the OpenAICompatibleProvider mixin / external callers to set
        # base_url; treat it as the local root (strip trailing /v1 if any).
        cleaned = (value or "").rstrip("/")
        if cleaned.endswith("/v1"):
            cleaned = cleaned[: -len("/v1")]
        self.base_url_root = cleaned or "http://127.0.0.1:11434"

    # ── Model catalogue (dynamic + safe fallback) ──────────────────────

    async def _refresh_remote_models(self, force: bool = False) -> list[str]:
        """Fetch the live model list from Ollama.

        Order of attempts:
          1. /v1/models (OpenAI-compat, modern Ollama)
          2. /api/tags (legacy Ollama endpoint, returns {"models": [...]}
             with a ``name`` field per model)
        """
        now = time.time()
        if (
            not force
            and self._remote_models
            and (now - self._remote_models_fetched_at) < self._remote_models_ttl
        ):
            return self._remote_models

        ids: list[str] = []
        # 1. Try the OpenAI-compatible /v1/models path first
        try:
            ids = await self.fetch_remote_models()
        except Exception as e:  # noqa: BLE001
            logger.warning("[ollama] /v1/models refresh failed: %s", e)

        # 2. Safe fallback: legacy /api/tags (older Ollama versions)
        if not ids:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{self.base_url_root}/api/tags",
                        timeout=10.0,
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    ids = [m["name"] for m in data.get("models", []) if m.get("name")]
            except Exception as e:  # noqa: BLE001
                logger.warning("[ollama] /api/tags fallback failed: %s", e)

        if ids:
            self._remote_models = sorted(set(ids))
            self._remote_models_fetched_at = now
        return self._remote_models

    async def get_models(self) -> list[str]:
        """Return the current best-known Ollama model list.

        Strategy: cached remote list (refreshed every 5 min), with the
        small _PREFERRED_OLLAMA_MODELS whitelist hoisted to the top so
        the provider is never completely empty.
        """
        remote = await self._refresh_remote_models()
        if not remote:
            return list(_PREFERRED_OLLAMA_MODELS)
        preferred_present = [m for m in _PREFERRED_OLLAMA_MODELS if m in remote]
        preferred_only = [m for m in _PREFERRED_OLLAMA_MODELS if m not in remote]
        return preferred_present + remote + preferred_only

    # ── Shared param building ──────────────────────────────────────────

    def _build_params(
        self, model: str, messages: list[dict], stream: bool, **kwargs
    ) -> tuple[list[dict], dict, float]:
        temperature = kwargs.get("temperature", 0.69)
        top_p = kwargs.get("top_p", 0.7)
        top_k = kwargs.get("top_k", 40)
        typical_p = kwargs.get("typical_p", 0.8)
        num_ctx = kwargs.get("num_ctx", 8192)
        timeout = float(kwargs.get("timeout", self._default_timeout))

        # Ollama accepts these sampling/option knobs as top-level fields on
        # /api/chat, but on the OpenAI-compat path we forward them as
        # extras and let the server decide which ones it understands.
        extra: dict = {}
        if top_k is not None:
            extra["top_k"] = top_k
        if typical_p is not None:
            extra["typical_p"] = typical_p
        if num_ctx is not None:
            extra["num_ctx"] = num_ctx

        return messages, {
            "temperature": temperature,
            "top_p": top_p,
            "extra": extra,
        }, timeout

    # ── Public send_message (text) ─────────────────────────────────────

    async def send_message(
        self, messages: list[dict], model: str, **kwargs
    ) -> str | None:
        self._last_source = kwargs.get("source", "llm")
        try:
            messages, params, _timeout = self._build_params(
                model, messages, False, **kwargs
            )
            raw = await self._chat_complete(
                model,
                messages,
                temperature=params["temperature"],
                top_p=params["top_p"],
                extra=params["extra"],
            )
            content = raw["choices"][0]["message"]["content"]
            return (content or "").strip()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[Ollama] send_message error: {e}")
            return None

    # ── Public send_message_raw (full response dict) ───────────────────

    async def send_message_raw(
        self, messages: list[dict], model: str, **kwargs
    ) -> dict | None:
        self._last_source = kwargs.get("source", "llm")
        try:
            messages, params, _timeout = self._build_params(
                model, messages, False, **kwargs
            )
            raw = await self._chat_complete(
                model,
                messages,
                temperature=params["temperature"],
                top_p=params["top_p"],
                extra=params["extra"],
            )
            self._last_raw_response = raw
            return raw
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[Ollama] send_message_raw error: {e}")
            return None

    # ── Streaming ──────────────────────────────────────────────────────

    async def send_message_streaming(
        self, messages: list[dict], model: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        self._last_source = kwargs.get("source", "llm")
        try:
            messages, params, _timeout = self._build_params(
                model, messages, True, **kwargs
            )
            async for content, event in self._chat_stream(
                model,
                messages,
                temperature=params["temperature"],
                top_p=params["top_p"],
                extra=params["extra"],
            ):
                if content is not None:
                    yield content
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            yield f"Error: {str(e)}"
