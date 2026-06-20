---
name: provider-rate-limiting-standard
description: |
  Standard for the provider-level and model-level rate limiting
  infrastructure in `app/providers/base.py`. Covers the two-tier semaphore
  design (provider + per-model), per-event-loop semaphore recreation
  pattern, the `_rate_limit_provider` async context manager, exponential
  backoff retry on 429, and the `source` parameter for log/metric
  disambiguation. Use when adding a new provider, debugging 429 errors,
  changing rate-limit delays, or wiring a new call site (embedding, PCL,
  memory pipeline) through the rate limiter. Does NOT cover: provider
  class hierarchy (see `provider-integration-standard` — pending), model
  selection, or the deprecated shim surface.
---

# Provider Rate Limiting Standard

> **Scope**: rate-limit infrastructure in `app/providers/base.py`.
> **Authority**: This skill is local to the provider layer; it does not
> override the Constitution or `codebase-navigation`.

---

## 1. The Two-Tier Design

The rate limiter uses two independent tiers, acquired in order:

| Tier | Scope | Delay (seconds) | Recreated per loop? |
|---|---|---|---|
| **Provider** | All calls to a given provider name (e.g., "chutes") | 0.5s chutes, 0.3s openrouter, 0.1s ollama, 0.5s default | Yes |
| **Model** | All calls to a given model name (any provider) | 1.0s | Yes |

**Why two tiers:**

- The provider tier enforces the upstream account's global rate (e.g., Chutes' per-account QPS).
- The model tier prevents bursts against a single model even if you switch providers (e.g., `Qwen3-Embedding-8B` via Chutes and via a future OpenAI-compatible mirror).

**Rules:**

- Provider tier is acquired **first**, then model tier, then the HTTP call runs.
- Both are released in reverse order automatically by `async with`.
- Between the two acquisitions, the delay check happens — the model tier delay is enforced *after* the provider delay.

**Anti-pattern (DO NOT):**

- Acquiring only the model tier because "the provider delay is the same anyway" — the provider tier is the safety net for account-wide throttling.
- Adding a per-call tier (e.g., per-prompt) — over-throttling hurts throughput without adding safety.

---

## 2. The `_rate_limit_provider` Context Manager

Public API (in `app/providers/base.py`):

```python
@asynccontextmanager
async def _rate_limit_provider(
    provider: str,
    model: str,
    source: str = "llm",
):
    """Async context manager that acquires both tiers and enforces delays.

    Args:
        provider: Provider name (e.g., "chutes", "openrouter", "ollama")
        model: Model name for the per-model tier
        source: Caller context for logging (e.g., "llm", "embedding",
                "pcl_memory", "memory_pipeline")
    """
```

**Rules:**

- `provider` MUST be one of the keys in `_PROVIDER_RATE_LIMITS`, or it falls back to the `"default"` delay (currently 0.5s).
- `model` MUST be a non-empty string. Pass the actual model name, not a placeholder.
- `source` is a **free-form log tag** that goes into `logger.info(f"[{source.upper()}] Requesting ...")`. Use one of:
  - `"llm"` — primary chat path
  - `"embedding"` — `app/memory/embedder.py` calls
  - `"pcl_memory"` — Predict-Calibrate Learning memory pipeline
  - `"memory_pipeline"` — segmentation / extraction
  - `"helper"` — `chutes_chat()` direct helper calls
- The context manager updates `_PROVIDER_LAST_CALL[provider]` and `_MODEL_LAST_CALL[model]` in the `finally` block — this happens even on exception.

**Anti-pattern (DO NOT):**

- Using `source=""` or `source="unknown"` — the log line is the only way to attribute 429s in production.
- Calling `_rate_limit_provider` from inside a sync function — the whole thing is async; there is no sync version.
- Wrapping a non-HTTP operation in `_rate_limit_provider` (e.g., a local computation) — it serves no purpose and consumes the slot.

---

## 3. Per-Event-Loop Semaphore Recreation

Semaphores in asyncio are bound to the event loop that created them. If a new loop starts (e.g., FastAPI reload, test isolation), the old semaphores must be discarded or you get `RuntimeError: ... attached to a different loop`.

**The pattern (in `_get_provider_semaphore_async` and `_get_model_semaphore_async`):**

```python
current_loop_id = id(asyncio.get_event_loop())

if provider in _PROVIDER_SEMAPHORES:
    if _SEMAPHORE_LOOPS.get(provider) == current_loop_id:
        return _PROVIDER_SEMAPHORES[provider]
    # Loop changed - recreate semaphore
    logger.debug(f"[RateLimit] Event loop changed for {provider}, recreating semaphore")

# Create new semaphore in current loop
_PROVIDER_SEMAPHORES[provider] = asyncio.Semaphore(1)
_SEMAPHORE_LOOPS[provider] = current_loop_id
return _PROVIDER_SEMAPHORES[provider]
```

**Rules:**

- The loop id is captured via `id(asyncio.get_event_loop())` — this is intentionally cheap and re-evaluated on every call.
- `_SEMAPHORE_LOOPS` is a `dict[str, int]` keyed the same way as the semaphore dict (`provider` for provider tier, `f"model:{model}"` for model tier).
- Recreate on mismatch — never try to rebind an existing semaphore to a new loop.
- The provider tier uses `provider` as the key; the model tier uses `f"model:{model}"` to avoid collision with provider names like `"model:..."`.

**Anti-pattern (DO NOT):**

- Creating semaphores at module import time — they'll bind to whatever loop was active at import, which is wrong under FastAPI's reload.
- Caching the semaphore by `id()` only (no loop tracking) — works for one loop, breaks on reload.
- Using `asyncio.Lock` instead of `asyncio.Semaphore(1)` — semaphores with capacity 1 are explicit about the concurrency contract.

---

## 4. Retry on 429 — The Backoff Pattern

The `_retry_with_backoff` helper (in `app/providers/base.py`) handles 429 responses with exponential backoff **outside** the rate-limit lock, so other requests can proceed during the wait.

```python
async def _retry_with_backoff(
    func,
    provider: str,
    model: str,
    max_retries: int = 3,
    backoff_base: float = 2.0,
    **kwargs,
):
    ...
    for attempt in range(max_retries):
        ...
        async with _rate_limit_provider(provider, model):
            result = await func(**kwargs)
            if isinstance(result, tuple) and result[0] == 429:
                should_retry = True
        if should_retry and attempt < max_retries - 1:
            await asyncio.sleep(backoff_base * (2 ** attempt))
            continue
        return result
```

**Rules:**

- Backoff happens **outside** the `async with _rate_limit_provider` block — the slot is released, another request can take it.
- Default backoff sequence: `2s, 4s, 8s` (3 retries total).
- The function-under-test (`func`) MUST return either a success value or a tuple whose first element is the HTTP status code, so 429s are detectable.
- After `max_retries` attempts, the last error is raised with `f"Max retries ({max_retries}) exceeded: {last_error}"`.

**Anti-pattern (DO NOT):**

- Sleeping inside the lock — blocks other requests for the full backoff duration.
- Using a constant backoff (e.g., always 5s) — exponential gives the upstream more breathing room as the rate-limit window widens.
- Catching `asyncio.CancelledError` inside the retry loop — the request is being torn down; propagate it.

---

## 5. `chutes_chat()` — The Direct HTTP Helper

`app/llm_client.py:chutes_chat` is a **direct HTTP bypass** of the provider manager for cases where the manager would be overkill (single-turn helpers, internal LLM calls, debug). It STILL uses the rate limiter.

**Rules:**

- `chutes_chat` MUST acquire `_rate_limit_provider("chutes", candidate, source=source)` per candidate per retry.
- `source` is the only place to distinguish "helper" from "llm" calls in logs — pass it through.
- On 429, the helper retries the **same** candidate with `backoff_base ** retry` delay (1s, 2s, 4s) up to `max_429_retries` times before moving to the next fallback.
- Fallback models are tried in order, each with their own retry budget.

**Anti-pattern (DO NOT):**

- Adding a new direct HTTP helper for a different provider — use the manager (`ai_manager.send_message`) instead so rate-limit + retry is centralized.
- Skipping `_rate_limit_provider` in `chutes_chat` "because it's a helper" — helpers share the same upstream account as the LLM path.

---

## 6. The 429 Source Tag

Use the `source` parameter in `_rate_limit_provider` to attribute 429s in logs. The current log line is:

```
[{source.upper()}] Requesting {provider}/{model}...
```

So `source="embedding"` logs as `[EMBEDDING] Requesting chutes/Qwen3-Embedding-8B...`. This is the only way to tell at a glance whether 429s are coming from chat, embedding, or memory pipeline.

**Anti-pattern (DO NOT):**

- Using `source` for any other purpose (e.g., passing an exception message). It's a category tag, not a free-form string.
- Logging the source separately from the rate-limit entry — the rate-limit context manager already logs it; duplicating adds noise.

---

## 7. Adding a New Provider to the Rate Limit Table

If you add a new provider (e.g., `"groq"`):

1. Add the key to `_PROVIDER_RATE_LIMITS` in `app/providers/base.py` with a conservative delay (start with `"default"`'s 0.5s).
2. Add a new branch in `_get_provider_semaphore_async` — actually, no: the `if provider in _PROVIDER_SEMAPHORES` check handles new keys automatically.
3. Wire the new provider through `_load_providers` (in `app/providers/__init__.py`).
4. Add an `AVAILABLE_MODELS` list to the new provider class.

**Anti-pattern (DO NOT):**

- Adding a hardcoded `if provider == "groq"` branch in `_rate_limit_provider` — the `dict.get(provider, _PROVIDER_RATE_LIMITS["default"])` fallback already handles it.
- Setting a 0s delay for a "fast" provider — even fast providers have account-wide rate limits; the tier is the safety net.

---

## 8. Pre-Push Checklist for Rate-Limit Changes

- [ ] If you changed `_PROVIDER_RATE_LIMITS` delays, documented why (e.g., upstream SLA change)
- [ ] If you changed `_MODEL_RATE_LIMIT`, the change applies to ALL models, not just the one you were debugging
- [ ] If you added a new `source` tag, updated any log-search queries that filter on the old tags
- [ ] No semaphores are created at module import time
- [ ] `_retry_with_backoff` still releases the lock before sleeping
- [ ] `ruff check .` and `python3 -m py_compile app/providers/base.py` pass
- [ ] If you added a new call site (e.g., a new tool that calls Chutes directly), the call is wrapped in `_rate_limit_provider` with a unique `source` tag
