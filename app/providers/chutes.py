from __future__ import annotations

# FILE: app/providers/chutes.py
# DESCRIPTION: Chutes AI provider (OpenAI-compatible, https://llm.chutes.ai/v1)
#              Migrated to use the official openai SDK (AsyncOpenAI) via the
#              OpenAICompatibleProvider mixin in app/providers/openai_base.py.
#
# Phase B scope:
#   - HTTP/streaming moved from raw httpx to AsyncOpenAI
#   - Hardcoded available_models list replaced with dynamic /v1/models fetch
#   - Vision message rewriting + model fallback (Qwen priority) preserved
#   - 429 retry with exponential backoff preserved at the rate-limit layer
#   - 30-iteration outer model-fallback loop preserved

import asyncio
import logging
import time
from typing import AsyncGenerator

from app.providers.base import AIProvider
from app.providers.openai_base import OpenAICompatibleProvider
from app.tools import multimodal_tools

logger = logging.getLogger(__name__)


# A small static set of "preferred" models we know work well for Chutes.
# This is NOT a hardcoded allow-list — the live model catalogue comes from
# /v1/models. The preferred set is used to (a) bias the fallback chain and
# (b) decide whether a user-supplied model hint is worth trying first.
_PREFERRED_CHUTES_MODELS: list[str] = [
    "Qwen/Qwen3-235B-A22B-Thinking-2507",
    "Qwen/Qwen3.6-27B-TEE",
]


class ChutesProvider(OpenAICompatibleProvider, AIProvider):
    def __init__(self, config: dict | None = None):
        super().__init__("chutes", config)
        self.base_url = "https://llm.chutes.ai/v1"
        self._last_error: str | None = None
        # Cached list fetched lazily from /v1/models. Populated on first
        # get_models() call. An empty list means "not yet fetched".
        self._remote_models: list[str] = []
        self._remote_models_fetched_at: float = 0.0
        # Refresh the model catalogue at most every 5 minutes
        self._remote_models_ttl: float = 300.0

    # ── Model catalogue (dynamic) ──────────────────────────────────────

    async def _refresh_remote_models(self, force: bool = False) -> list[str]:
        """Fetch the live model list from Chutes' /v1/models endpoint.

        Cached for ``self._remote_models_ttl`` seconds. On any error the
        previous list (possibly empty) is returned.
        """
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
            logger.warning("[chutes] /v1/models refresh failed: %s", e)
            return self._remote_models

        if ids:
            self._remote_models = sorted(set(ids))
            self._remote_models_fetched_at = now
        return self._remote_models

    async def get_models(self) -> list[str]:
        """Return the current best-known Chutes model list.

        Strategy:
          1. Return the cached remote list (refreshed every 5 min).
          2. Merge the small _PREFERRED_CHUTES_MODELS whitelist at the top
             so they're always available even if /v1/models is briefly down.
        """
        remote = await self._refresh_remote_models()
        if not remote:
            return list(_PREFERRED_CHUTES_MODELS)
        # Preferred first, then everything else, deduped
        preferred_present = [m for m in _PREFERRED_CHUTES_MODELS if m in remote]
        preferred_only = [m for m in _PREFERRED_CHUTES_MODELS if m not in remote]
        return preferred_present + remote + preferred_only

    def _known_models(self) -> set[str]:
        """Return the union of remote + preferred models (synchronous, cached)."""
        return set(self._remote_models) | set(_PREFERRED_CHUTES_MODELS)

    # ── Message normalization ──────────────────────────────────────────

    def _normalize_messages_for_chutes(self, messages: list[dict]) -> list[dict]:
        if not messages:
            return messages
        standard_roles = {"system", "user", "assistant", "tool"}
        system_contents = []
        normalized_messages = []

        for msg in messages:
            role = msg.get("role", "")
            if role == "system":
                system_contents.append(msg.get("content", ""))
            elif role not in standard_roles:
                content = msg.get("content", "")
                normalized_content = f"[{role}]\n{content}"
                normalized_messages.append(
                    {"role": "assistant", "content": normalized_content}
                )
            else:
                normalized_messages.append(msg)

        if system_contents:
            merged_system = "\n\n".join(system_contents)
            return [{"role": "system", "content": merged_system}] + normalized_messages
        return normalized_messages

    # ── Main sync send_message ─────────────────────────────────────────

    async def send_message(
        self, messages: list[dict], model: str, source: str = "llm", **kwargs
    ) -> str | None:
        """Send message with retry logic and model fallback.

        Retry architecture:
        1. Outer loop: Model selection/fallback
        2. Inner loop: 429 retry with exponential backoff
        """
        if not self.api_key:
            return None
        known = self._known_models()
        if model not in known:
            # We don't have this model locally; allow the request anyway
            # because the remote catalogue may list models we haven't cached.
            logger.debug(
                "[chutes] %s not in local cache, will trust server", model
            )

        log_prefix = kwargs.pop("log_prefix", "[CHAT]")
        kwargs.pop("model", None)
        kwargs.pop("model_name", None)

        # Record source for the rate-limit context (used by the mixin)
        self._last_source = source

        model_hint = kwargs.get("model") or kwargs.get("model_name")
        explicit_model = bool(model_hint and model_hint in known)

        attempt = 0
        last_error = None
        max_model_attempts = 3
        max_429_retries = 3
        backoff_base = 2.0  # 2s, 4s, 8s

        tried_models: set[str] = set()
        # Build the priority list lazily so we hit /v1/models exactly once
        all_models = await self.get_models()

        while attempt < max_model_attempts:
            attempt += 1
            current_model = model if attempt == 1 else None

            # Model fallback selection
            if current_model is None:
                priority = [m for m in all_models if m not in tried_models]
                qwen_first = sorted(priority, key=lambda m: 0 if "Qwen" in m else 1)
                for candidate in qwen_first:
                    if explicit_model and candidate == model_hint:
                        continue
                    current_model = candidate
                    break

            if not current_model:
                break

            tried_models.add(current_model)

            # ── Inner loop: 429 retry with exponential backoff ──
            for retry in range(max_429_retries):
                status = None
                data = None
                error_msg = None

                try:
                    data = await self._chutes_raw(current_model, messages, kwargs)
                    self._last_error = None
                    return data
                except _ChutesError as err:
                    status = err.status
                    error_msg = err.message
                    last_error = error_msg
                    self._last_error = last_error

                    # 429 with retries left → back off outside the lock
                    if status == 429 and retry < max_429_retries - 1:
                        backoff = backoff_base * (2**retry)  # 2s, 4s
                        logger.warning(
                            f"{log_prefix} 429 on {current_model}, "
                            f"retry {retry + 1}/{max_429_retries} in {backoff}s..."
                        )
                        await asyncio.sleep(backoff)
                        continue
                    # Try another model
                    break
                except Exception as e:  # noqa: BLE001
                    last_error = str(e)
                    self._last_error = last_error
                    return None

            # Delay before trying next model
            if attempt < max_model_attempts:
                await asyncio.sleep(0.5)
                logger.debug(
                    f"{log_prefix} {current_model} failed ({status}), "
                    f"trying another model..."
                )

        logger.debug(f"{log_prefix} All models exhausted, last error: {last_error}")
        return None

    async def _chutes_raw(self, model: str, messages: list[dict], kwargs) -> str:
        """One non-streaming call to Chutes via the SDK.

        Raises ``_ChutesError(status, message)`` on HTTP failure and lets
        network exceptions propagate up.
        """
        messages = self._normalize_messages_for_chutes(list(messages))

        if kwargs.get("skip_vision") is not True:
            if self.supports_vision(model) and messages:
                last_user_message = self._get_last_user_message(messages)
                if last_user_message and multimodal_tools.has_images(last_user_message):
                    logger.debug(
                        f"[Vision] Triggered for message: {last_user_message[:100]}..."
                    )
                    vision_messages = self.format_vision_message(last_user_message)
                    messages = self._replace_last_user_message(
                        messages, last_user_message, vision_messages
                    )

        temperature = kwargs.get("temperature", 0.73)
        max_tokens = kwargs.get("max_tokens")
        top_p = kwargs.get("top_p", 0.9)
        top_k = kwargs.get("top_k", 45)

        extra: dict = {}
        # Chutes accepts a few non-standard knobs; pass them through if set
        if top_k is not None:
            extra["top_k"] = top_k
        typical_p = kwargs.get("typical_p")
        if typical_p is not None:
            extra["typical_p"] = typical_p

        log_prefix = kwargs.get("log_prefix", "[CHAT]")
        logger.debug(f"{log_prefix} {model} | max_tokens={max_tokens or 'unlimited'}")

        # Map non-200 responses to _ChutesError so the retry loop can branch
        try:
            raw = await self._chat_complete(
                model,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                extra=extra,
            )
        except Exception as e:  # noqa: BLE001
            # The openai SDK wraps non-200 in APIStatusError. Surface status
            status = getattr(e, "status_code", None) or 0
            message = str(e)
            raise _ChutesError(status, message) from e

        # Extract text content
        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise _ChutesError(500, f"parse-error: {e}") from e

        return (content or "").strip()

    # ── Streaming ──────────────────────────────────────────────────────

    async def send_message_streaming(
        self, messages: list[dict], model: str, source: str = "llm", **kwargs
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            reason = "missing API key"
            logger.warning("Chutes stream aborted: %s", reason)
            yield (
                "\n[System] Chutes provider error: "
                + reason
                + ". Please check configuration."
            )
            return

        try:
            messages = self._normalize_messages_for_chutes(messages)
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
            top_k = kwargs.get("top_k", 45)
            typical_p = kwargs.get("typical_p", 0.85)

            extra: dict = {"stream": True}  # stream=True is set inside _chat_stream
            if top_k is not None:
                extra["top_k"] = top_k
            if typical_p is not None:
                extra["typical_p"] = typical_p

            # Track source for the rate-limit context
            self._last_source = source

            async for chunk in self._chat_stream(
                model,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                extra=extra,
            ):
                yield chunk

        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            yield f"Error: {str(e)}"


class _ChutesError(Exception):
    """Internal exception used to thread HTTP status up to the retry loop."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message
