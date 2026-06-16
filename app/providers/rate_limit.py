from __future__ import annotations

# FILE: app/providers/rate_limit.py
# DESCRIPTION: Extracted rate-limit machinery shared by all providers.
#              This module is a pure refactor: the symbols (_rate_limit_provider,
#              _retry_with_backoff, _PROVIDER_* dicts) are moved here from
#              app/providers/base.py unchanged, and re-exported from base.py for
#              backwards compatibility with existing import sites.
#
# Behavior MUST be preserved bit-for-bit during the migration.

import asyncio
import logging
import time
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# ── Provider-level rate limiting (generalized) ───────────────────────────────
# Each provider gets its own semaphore and rate limit config
# CRITICAL: Semaphores MUST be created per-event-loop to prevent cross-loop binding

_PROVIDER_SEMAPHORES: dict[str, asyncio.Semaphore] = {}
_PROVIDER_LAST_CALL: dict[str, float] = {}
_PROVIDER_RATE_LIMITS: dict[str, float] = {
    "chutes": 0.5,  # 0.5s between Chutes requests (strict)
    "openrouter": 0.3,  # 0.3s between OpenRouter requests
    "ollama": 0.1,  # 0.1s for local Ollama (relaxed)
    # Default for unknown providers
    "default": 0.5,
}

# ── Model-level rate limiting ───────────────────────────────────────────────

_MODEL_SEMAPHORES: dict[str, asyncio.Semaphore] = {}
_MODEL_LAST_CALL: dict[str, float] = {}
_MODEL_RATE_LIMIT = 1.0  # Min 1s between calls to same model

# Track which event loop each semaphore belongs to
_SEMAPHORE_LOOPS: dict[str, int] = {}  # semaphore_key -> loop_id


async def _get_provider_semaphore_async(provider: str) -> asyncio.Semaphore:
    """Get or create a semaphore for a specific provider (async).

    CRITICAL: Creates semaphore in current event loop to prevent cross-loop binding.
    If the event loop changed (e.g., after FastAPI reload), recreate the semaphore.
    """
    current_loop_id = id(asyncio.get_event_loop())

    # Check if semaphore exists and belongs to current loop
    if provider in _PROVIDER_SEMAPHORES:
        if _SEMAPHORE_LOOPS.get(provider) == current_loop_id:
            return _PROVIDER_SEMAPHORES[provider]
        # Loop changed - recreate semaphore
        logger.debug(
            f"[RateLimit] Event loop changed for {provider}, recreating semaphore"
        )

    # Create new semaphore in current loop
    _PROVIDER_SEMAPHORES[provider] = asyncio.Semaphore(1)
    _SEMAPHORE_LOOPS[provider] = current_loop_id
    return _PROVIDER_SEMAPHORES[provider]


async def _get_model_semaphore_async(model: str) -> asyncio.Semaphore:
    """Get or create a semaphore for a specific model (async).

    CRITICAL: Creates semaphore in current event loop to prevent cross-loop binding.
    """
    current_loop_id = id(asyncio.get_event_loop())
    sem_key = f"model:{model}"

    if sem_key in _MODEL_SEMAPHORES:
        if _SEMAPHORE_LOOPS.get(sem_key) == current_loop_id:
            return _MODEL_SEMAPHORES[sem_key]
        # Loop changed - recreate semaphore
        logger.debug(
            f"[RateLimit] Event loop changed for model {model}, recreating semaphore"
        )

    _MODEL_SEMAPHORES[model] = asyncio.Semaphore(1)
    _SEMAPHORE_LOOPS[sem_key] = current_loop_id
    return _MODEL_SEMAPHORES[model]


@asynccontextmanager
async def _rate_limit_provider(provider: str, model: str, source: str = "llm"):
    """Context manager for provider-level rate limiting.

    Args:
        provider: Provider name (e.g., "chutes", "openrouter")
        model: Model name for per-model rate limiting
        source: Source context for logging (e.g., "chat", "pcl_memory", "embedding")
    """
    provider_sem = await _get_provider_semaphore_async(provider)
    model_sem = await _get_model_semaphore_async(model)

    # Acquire provider-global semaphore first
    async with provider_sem:
        # Enforce provider-level delay
        provider_delay = _PROVIDER_RATE_LIMITS.get(
            provider, _PROVIDER_RATE_LIMITS["default"]
        )
        if provider in _PROVIDER_LAST_CALL:
            elapsed = time.time() - _PROVIDER_LAST_CALL[provider]
            if elapsed < provider_delay:
                await asyncio.sleep(provider_delay - elapsed)

        # Acquire model-specific semaphore
        async with model_sem:
            # Enforce model-level delay
            if model in _MODEL_LAST_CALL:
                elapsed = time.time() - _MODEL_LAST_CALL[model]
                if elapsed < _MODEL_RATE_LIMIT:
                    await asyncio.sleep(_MODEL_RATE_LIMIT - elapsed)

            # Log the action with context
            logger.info(f"[{source.upper()}] Requesting {provider}/{model}...")

            try:
                yield
            finally:
                # Update timestamps
                _PROVIDER_LAST_CALL[provider] = time.time()
                _MODEL_LAST_CALL[model] = time.time()


# ── Retry with exponential backoff (429 handling) ─────────────────────────────


async def _retry_with_backoff(
    func,
    provider: str,
    model: str,
    max_retries: int = 3,
    backoff_base: float = 2.0,
    **kwargs,
):
    """Execute function with retry logic for 429 errors.

    IMPORTANT: This function releases the rate limit lock BEFORE sleeping,
    allowing other requests to proceed during the backoff period.

    Args:
        func: Async function to call (e.g., _chutes_raw)
        provider: Provider name for rate limiting
        model: Model name for rate limiting
        max_retries: Maximum retry attempts (default: 3)
        backoff_base: Base backoff in seconds (default: 2.0, doubles each retry)
        **kwargs: Arguments to pass to func

    Returns:
        Result from func, or raises exception after max retries

    Example backoff sequence: 2s, 4s, 8s (if max_retries=3)
    """
    last_error = None

    for attempt in range(max_retries):
        should_retry = False
        backoff = backoff_base * (2**attempt) if attempt > 0 else 0

        try:
            async with _rate_limit_provider(provider, model):
                result = await func(**kwargs)

                # Check if result indicates 429
                if isinstance(result, tuple) and len(result) >= 1:
                    status = result[0]
                    if status == 429:
                        should_retry = True
                        last_error = "HTTP 429: Rate limited"
                        logger.warning(
                            f"[{provider}] 429 on {model}, "
                            f"attempt {attempt + 1}/{max_retries}"
                        )

        except Exception as e:
            last_error = str(e)
            logger.error(f"[{provider}] Request failed: {e}")
            raise

        if should_retry and attempt < max_retries - 1:
            # Sleep OUTSIDE the lock to not block other requests
            logger.info(f"[{provider}] Backing off for {backoff}s...")
            await asyncio.sleep(backoff)
            continue

        return result

    raise Exception(f"Max retries ({max_retries}) exceeded: {last_error}")


__all__ = [
    "_rate_limit_provider",
    "_retry_with_backoff",
    "_PROVIDER_SEMAPHORES",
    "_PROVIDER_LAST_CALL",
    "_PROVIDER_RATE_LIMITS",
    "_MODEL_SEMAPHORES",
    "_MODEL_LAST_CALL",
    "_MODEL_RATE_LIMIT",
    "_SEMAPHORE_LOOPS",
]
