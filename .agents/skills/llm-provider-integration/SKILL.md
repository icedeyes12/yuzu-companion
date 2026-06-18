---
name: llm-provider-integration
description: Standards for adding or maintaining LLM providers in yuzu-companion. Use when touching app/providers/, app/llm_client.py, streaming model dispatch, or provider-specific model selection.
compatibility: Created for Zo Computer
metadata:
  author: yuzu.zo.computer
---
# LLM Provider Integration Standards

## Scope
Covers provider classes in `file 'app/providers/'`, provider registration, streaming behavior, and the LLM dispatch helpers in `file 'app/llm_client.py'` and `file 'app/stream_manager.py'`.
Does **not** override the base runtime or database constitutions.

## 1. Base Inheritance
- All current providers subclass `OpenAICompatibleProvider` in `file 'app/providers/base.py'`.
- Keep subclasses thin: set `name`, `base_url`, optional `default_headers` in `__init__`, and expose an `AVAILABLE_MODELS` class attribute. Override `chat_complete()` / `chat_stream()` **only** when the provider needs provider-specific behavior (see `file 'app/providers/openrouter.py'` for the canonical override that injects `extra_body` and caps `:free` models).
- Override `get_models()` to return a hardcoded list when the upstream `/v1/models` is unreliable (`file 'app/providers/chutes.py'`, `file 'app/providers/cerebras.py'`, `file 'app/providers/openrouter.py'`). Override `test_connection()` only when a native health endpoint is better than the OpenAI one (`file 'app/providers/ollama.py'`).

## 2. Primary vs Deprecated Interface
- The **primary** interface is `chat_complete()` returning `openai.types.chat.ChatCompletion` and `chat_stream()` yielding `ChatCompletionChunk`.
- `send_message()`, `send_message_raw()`, `send_message_streaming()` are **DEPRECATED shims** that bridge to the new interface. Do not build new call paths on them.
- New dispatch code in `file 'app/llm_client.py'` calls `provider_instance.chat_complete(...)` / `provider_instance.chat_stream(...)` directly — follow that pattern, not the manager-level shims.
- The manager (`AIProviderManager`) still exposes only the deprecated shims at the manager level; call the provider instance's primary methods directly when you need structured output.

## 3. Rate Limiting and Semaphores
- Use `_rate_limit_provider(provider, model, source)` (`asynccontextmanager` in `file 'app/providers/base.py'`) for every outbound LLM/embedding call.
- Semaphores are **per event loop**. The helpers `_get_provider_semaphore_async` / `_get_model_semaphore_async` recreate a semaphore when `asyncio.get_event_loop()` identity changes. Never bind a semaphore across loops and never instantiate `asyncio.Semaphore` at module import time.
- Handle HTTP 429 with `_retry_with_backoff`. The lock **must** be released before the backoff sleep so other requests can proceed — keep that invariant if you touch the retry path.

## 4. Streaming and Buffer Architecture
- `file 'app/stream_manager.py'` owns live stream state. `StreamBuffer` accumulates chunks in RAM and fans them out to subscriber queues.
- Do **not** write chunks to the database during active generation.
- Persistence contract is **split by outcome**:
  - **Success**: the orchestrator owns the final DB write. `StreamBuffer._process()` has its success persist call intentionally commented out.
  - **Cancellation / error**: `StreamBuffer._persist_to_db(..., is_error=True)` writes the partial content with an interruption marker from the `finally`/`except` path.
- Preserve `asyncio.CancelledError` propagation through `_stream_from_provider` and the provider shims — never swallow cancellation. Re-raise it.
- Cleanup: `StreamBuffer._cleanup_loop` removes finished streams after 5 min of inactivity and force-cancels streams inactive for 30 min.

## 5. Standalone Chutes Helper
- `chutes_chat()` in `file 'app/llm_client.py'` is a raw `httpx` single-turn helper (used by memory review / summarization), separate from the provider class. It uses `_rate_limit_provider("chutes", ...)` and its own 429 backoff. When you need a one-shot LLM call, prefer this helper over spinning up a provider call.

## 6. Internal Fallback Call
- `AIProviderManager._internal_llm_call()` / `auto_send_message()` is the curated fallback path (main model → fallback model with 1s cooldown). It reads `provider._last_error` to decide retryability — if you add a provider that participates in fallback, set `_last_error` on connection-class failures so the retry heuristic actually distinguishes retryable from fatal errors.

## Anti-Patterns
- Do not add a new provider by copying `OpenAICompatibleProvider` logic; subclass it.
- Do not call `chat_complete` / `chat_stream` from outside `file 'app/llm_client.py'` (the orchestrator and this module are the only sanctioned call sites).
- Do not log full request payloads at INFO (a stray `DEBUG CHUTES PAYLOAD` log currently dumps every streamed payload — do not replicate that pattern; remove it when encountered).
- Do not bind rate-limit semaphores across event loops.
