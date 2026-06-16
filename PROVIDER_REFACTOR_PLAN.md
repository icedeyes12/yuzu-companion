# Provider & Tool Refactor Plan

> **Phase 1 — Audit & Planning**
> **Date:** 2026-06-16
> **Scope:** Migrate all custom HTTP/REST LLM client logic to the official `openai` Python SDK (`AsyncOpenAI`), replace hardcoded model lists with dynamic fetching from `/v1/models`, and standardize all custom tools into the OpenAI `tools[]` JSON Schema format.
> **Status:** READ-ONLY audit complete. No executable code modified.

---

## 0. Current State (Key Findings)

The codebase is **closer to the target architecture than it appears**:

1. **Tool schema is already OpenAI-compatible.** `app/tools/schemas.py` defines `ToolDefinition` + `ToolParam` and `ToolDefinition.to_llm_schema()` (lines 28–51) already serializes to the exact OpenAI `function` tool format:
   ```json
   {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
   ```
   The registry exposes `get_tool_definitions()` (registry.py:181) and `_unique_tool_schemas()` (llm_client.py:140) already de-duplicates and passes that into `send_message_raw(..., tools=schemas)`.

2. **However, the LLM does not actually call tools natively.** The system prompt in `app/prompts.py` (lines 316, 339–360, 535–568) still instructs the model to emit `<command>...</command>` XML blocks. The orchestrator (`app/orchestrator.py`) parses those blocks via `parse_tool_blocks()` in `app/commands.py` and dispatches them through `execute_tool()` in `app/tools/registry.py`. The "native" path in `orchestrator._parse_raw_tool_calls_async` (line 217) only fires for `OpenRouterProvider.parse_tool_calls` (the only provider that has it implemented) and is otherwise a stub returning `[]` (`base.py:236`).

3. **All four LLM providers are hand-rolled HTTP/streaming wrappers** around `httpx` + `requests`, each with its own hardcoded `available_models: list[str]` and a per-provider `base_url`. There is no `/v1/models` discovery anywhere; `get_models()` simply returns the hardcoded list.

4. **The `openai` Python SDK is not a dependency.** `requirements.txt` and `pyproject.toml` have `requests` and `httpx` but no `openai` package.

5. **Vision-capable models are a third hardcoded list** in `app/tools/multimodal.py` (lines 29–36: `self.vision_models` dict), used by `get_available_vision_models()` and `get_best_vision_provider()` (line 546), and surfaced to the UI via `ConfigService.get_vision_payload()`.

6. **`<command>` block parser is the de facto tool protocol** — it splits single-string arguments, key=value pairs, JSON, and aliases (`imagine` → `image_generate`, `request` → `http_request`). All of this is "custom XML/text" parsing that the refactor must replace with native `tool_calls` interception.

---

## 1. Files Requiring Modification (Checklist)

### 1.1 LLM Provider Layer (HTTP → AsyncOpenAI)

| File | Lines | Required Change |
|---|---|---|
| `app/providers/base.py` | 1–471 | Replace `httpx`/`requests` plumbing in `AIProvider` with a thin wrapper around `openai.AsyncOpenAI`. Add abstract `get_models()` (already abstract), `chat_stream(messages, tools, tool_choice)` and `chat_complete(messages, tools, tool_choice)` abstract methods. Move `_rate_limit_provider` / `_retry_with_backoff` (lines 25–177) **out** of `base.py` into a new `app/providers/rate_limit.py` so they can wrap SDK calls. Keep `parse_tool_calls()` (line 236) — but make it operate on the SDK's `ChatCompletion` object directly. |
| `app/providers/chutes.py` | 1–317 | Replace `_chutes_raw`, `send_message`, and `send_message_streaming` (lines 60–315) with `AsyncOpenAI(base_url="https://llm.chutes.ai/v1", api_key=...)`. Replace `available_models` (lines 19–33) with dynamic fetch from `client.models.list()`. |
| `app/providers/openrouter.py` | 1–230 | Same migration. Add OpenRouter-specific headers (`HTTP-Referer`, `X-Title`) via `default_headers` on the client. Keep `parse_tool_calls()` (lines 212–229) — it already reads the OpenAI shape. |
| `app/providers/cerebras.py` | 1–136 | Same migration. Remove all `requests`/`httpx` imports. |
| `app/providers/ollama.py` | 1–119 | Special case: Ollama's `/api/chat` is **not** OpenAI-compatible, but it also exposes `/v1/chat/completions` and `/v1/models` since 0.3.x. Use `AsyncOpenAI(base_url=f"{self.base_url}/v1", api_key="ollama")` so we get a single code path. If `/v1/models` is unavailable on older Ollama, fall back to a manually-managed list per Ollama version. |
| `app/providers/__init__.py` | 1–38 | Unchanged. Still wires the four providers into `AIProviderManager`. |

### 1.2 LLM Client / Dispatcher

| File | Lines | Required Change |
|---|---|---|
| `app/llm_client.py` | 1–487 | **Refactor `_send_to_provider` (lines 207–278)** to call `provider.chat_complete()` which internally uses the SDK. **Replace `chutes_chat` helper (lines 30–130)** — its three duplicated call sites can collapse into a single SDK call. Drop the `import httpx` at line 12. |
| `app/llm_client.py` | 130–148 | `_unique_tool_schemas()` is already correct; no change needed. |
| `app/llm_client.py` | 207–278 | When `tools=schemas` is passed, change the dispatch to use `provider.chat_stream()` so the SDK yields chunks with `tool_call_delta` events. |
| `app/llm_client.py` | 363–416 | `_stream_from_provider` — change to iterate over `AsyncOpenAI` `chat.completions.create(..., stream=True)` chunks. |

### 1.3 Orchestrator (Native `tool_calls` Interception)

| File | Lines | Required Change |
|---|---|---|
| `app/orchestrator.py` | 217–236 | `_parse_raw_tool_calls_async` — generalize: stop calling `provider.parse_tool_calls()` (which only OpenRouter implements). Instead, walk the SDK's `ChatCompletion.choices[0].message.tool_calls` and build a uniform `[{"id", "name", "arguments"}]` list. |
| `app/orchestrator.py` | 240–259 | `_execute_tool_calls_async` — keep this function but ensure the result of tool execution is converted into SDK-shaped `tool` role messages (`{"role": "tool", "tool_call_id": ..., "content": str(result)}`) and stitched into `ephemeral_context` before the next LLM call. |
| `app/orchestrator.py` | 648–660 | The `<command>` fast-path in `handle_user_message` (the "user typed /imagine directly" branch) **must be deleted** once native `tool_calls` work — but see §6 for backwards-compat caveats. |
| `app/orchestrator.py` | 492–560 | `_run_orchestration_loop_async` — the loop currently re-runs `parse_tool_blocks(synthesis)` (line 537). After refactor, this becomes "check if the new assistant message contains any `tool_calls`; if so, execute, then re-invoke." |
| `app/orchestrator.py` | 311–333 | `_run_synthesis_async` and `_stream_synthesis_async` need to thread `tool_calls` results through `ephemeral_context` as proper `tool` role messages. |

### 1.4 Tool Protocol (Remove `<command>` Parser)

| File | Lines | Required Change |
|---|---|---|
| `app/commands.py` | 1–617 | **Delete or deprecate** `parse_tool_blocks`, `has_tool_blocks`, `_parse_command_string`, `_parse_args`, `_parse_key_value_args`, `execute_commands` (lines 95–610). Keep `parse_image_path`, `is_markdown_image_shortcut`, `extract_markdown_image_path` (lines 553–600) — those are for markdown post-processing, not tool dispatch. Keep `format_observation` if we still want a `<SYSTEM_OBSERVATION>` block in the assistant text. |
| `app/commands.py` | 28–29 | Delete `_TOOL_OPEN`/`_TOOL_CLOSE` constants and the entire custom string-split parser. |
| `app/orchestrator.py` | 10–17 | Drop the `parse_tool_blocks` / `execute_commands` imports once removed. |
| `app/prompts.py` | 316, 339–360, 512, 535–570 | Rewrite the system-prompt tool documentation to instruct the model to use the SDK's native `tool_calls` — no more `<command>` examples. Keep "system-injected `<tools>`" contract as the rendered output for the user. |
| `app/tools/registry.py` | 100–190 | `_collect_definitions()` and `get_tool_definitions()` already return OpenAI-shape objects — no change. Ensure alias resolution (`imagine` → `image_generate`) happens server-side on the inbound `tool_call.function.name`. |

### 1.5 Dynamic Model Discovery

| File | Lines | Required Change |
|---|---|---|
| `app/providers/base.py` | 218–221 | `get_models()` is already abstract — implement it in each provider via `client.models.list()`. |
| `app/providers/chutes.py` | 19–33, 62–64 | Delete `available_models` list. `get_models()` calls `await self._client.models.list()`. |
| `app/providers/openrouter.py` | 18–60, 62–64 | Same. |
| `app/providers/cerebras.py` | 16–27, 28–30 | Same. |
| `app/providers/ollama.py` | 14–26, 27–29 | Same (with version fallback). |
| `app/providers/base.py` | 175–183 | `get_all_models()` (line 384) and `get_provider_models()` (line 376) — add an async cache layer (see §3). |
| `app/services/config_service.py` | 41–55 | `get_ai_providers_payload` already calls `ai_manager.get_all_models()` — no change, it will automatically return live data. |
| `app/services/config_service.py` | 56–74 | `get_vision_payload` — replace `multimodal_tools.get_available_vision_models(provider)` (hardcoded `vision_models` dict) with a dynamic probe: query `/v1/models` and filter by provider metadata (`"modalities": ["text","image"]`) or by known vision-name patterns. |
| `app/tools/multimodal.py` | 29–36, 54–58, 546–614 | Delete `self.vision_models` dict. Add a `get_vision_models_async(provider)` method that hits the SDK's `models.list()` and applies a vision filter (e.g. substring match on `"vl"`, `"vision"`, `"kimi-k2.5"`, plus provider-returned modality tags). `get_best_vision_provider()` becomes async-aware. |
| `app/llm_client.py` | 234–238, 381–386 | Calls to `get_best_vision_provider()` need to be `await`ed. |

### 1.6 Misc Touches

| File | Lines | Required Change |
|---|---|---|
| `requirements.txt`, `pyproject.toml` | — | Add `openai>=1.50.0`. Remove `requests` if no longer used (still needed by `image_generate.py` and a few image tools — keep it for now). |
| `tests/test_commands.py` | — | The `<command>` parsing tests are obsolete. Replace with tests for `parse_tool_calls` on SDK objects. |
| `static/js/config.js` | 427, 461 | The UI consumes `models_by_provider` — no change needed; the shape is unchanged. |

---

## 2. Strategy: Replace Custom HTTP with `openai.AsyncOpenAI`

### 2.1 Construction

Each provider becomes a thin facade that holds an `AsyncOpenAI` client:

```python
# app/providers/chutes.py (after refactor — pseudo-code, NOT to be written yet)
class ChutesProvider(AIProvider):
    def __init__(self, config=None):
        super().__init__("chutes", config)
        self._client: AsyncOpenAI | None = None

    async def initialize(self) -> None:
        self.api_key = await self._load_api_key()
        if not self.api_key:
            self.is_available = False
            return
        self._client = AsyncOpenAI(
            base_url="https://llm.chutes.ai/v1",
            api_key=self.api_key,
            timeout=httpx.Timeout(120.0, connect=10.0),
            max_retries=0,  # we own retry via _retry_with_backoff
        )
        self.is_available = True

    async def get_models(self) -> list[str]:
        return await self._fetch_models_cached()

    async def _fetch_models_cached(self) -> list[str]:
        # See §3
        ...
```

### 2.2 Method Surface on `AIProvider`

Replace the existing `send_message` / `send_message_streaming` / `send_message_raw` with three SDK-shaped methods:

| New method | Returns | Replaces |
|---|---|---|
| `async chat_complete(messages, *, model, tools=None, tool_choice="auto", temperature, max_tokens, top_p, top_k, **kwargs) -> ChatCompletion` | The full SDK response object | `send_message_raw` (line 222 in `base.py`) |
| `async chat_stream(messages, *, model, tools=None, tool_choice="auto", **kwargs) -> AsyncIterator[ChatCompletionChunk]` | SDK chunk stream (includes `tool_call_delta` events) | `send_message_streaming` (line 232 in `base.py`) |
| `async chat_text(messages, *, model, **kwargs) -> str \| None` | Plain assistant text, used by internal `_internal_llm_call` and `chutes_chat` legacy helper | `send_message` (line 211 in `base.py`) |

### 2.3 SDK Identifiers

- `base_url` mapping:
  - Chutes: `https://llm.chutes.ai/v1`
  - OpenRouter: `https://openrouter.ai/api/v1`
  - Cerebras: `https://api.cerebras.ai/v1`
  - Ollama: `{self.base_url}/v1` (default `http://127.0.0.1:11434/v1`)
- `api_key`: from `await get_api_key_async(self.name)` — same as today. Encrypted at rest via `app/key_manager.py` (unchanged).
- Optional `default_headers`:
  - OpenRouter: `HTTP-Referer`, `X-Title` (lines 95–97 in `openrouter.py`) → set on the client.
  - Chutes: no extras.

### 2.4 Retry / Rate Limiting

`base.py:65–177` (`_rate_limit_provider`, `_retry_with_backoff`) **stays** — it doesn't know about HTTP. Wrap the SDK call site:

```python
# pseudo-code
async with _rate_limit_provider(provider_name, model, source=source):
    response = await self._client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        stream=False,
        **kwargs,
    )
```

The 429 / 5xx handling becomes:
1. Catch `openai.RateLimitError` / `openai.APIStatusError` per call.
2. Sleep **outside** the rate-limit lock (same pattern as today).
3. Advance to the next model in the fallback list (preserves existing `chutes.send_message` outer loop).

---

## 3. Architecture: Dynamic `/v1/models` + Caching

### 3.1 Data Flow

```
Frontend /api/config  ──┐
                         │
ConfigService           │
  ├─ get_ai_providers_payload
  │    └─ ai_manager.get_all_models()   ──> per-provider dynamic fetch (with cache)
  │
  └─ get_vision_payload
       └─ multimodal_tools.get_vision_models_async(provider)
                                                       │
                                                       ▼
                                       provider._fetch_models_cached()
                                                       │
                                            ┌──────────┴──────────┐
                                            │  in-memory TTL cache │
                                            │  (per provider)      │
                                            └──────────┬──────────┘
                                                       ▼
                                       openai.AsyncOpenAI.models.list()
```

### 3.2 Cache Layer (per provider)

Add to `app/providers/base.py` (or a new `app/providers/model_cache.py`):

```python
# pseudo-code — NOT to be written yet
_MODEL_CACHE_TTL = 600  # 10 min, configurable via env
_model_cache: dict[str, tuple[float, list[str]]] = {}

async def _fetch_models_cached(self) -> list[str]:
    key = self.name
    now = time.time()
    if key in _model_cache:
        ts, models = _model_cache[key]
        if now - ts < _MODEL_CACHE_TTL:
            return models
    try:
        page = await self._client.models.list()
        models = [m.id for m in page.data]
    except Exception as e:
        log.warning("model list failed for %s: %s", self.name, e)
        # Fall back to last known good list, then empty
        models = _model_cache.get(key, (0, []))[1]
    _model_cache[key] = (now, models)
    return models
```

### 3.3 Cache Invalidation

- **TTL-based:** 10 min default. Override via `YUZU_MODEL_CACHE_TTL` env var.
- **Manual invalidation:** `AIProviderManager.invalidate_model_cache(provider_name=None)` — call it when:
  - API key changes (`set_preferred_provider_async` in `config_service.py:139`).
  - User runs a `/reload` or `/models` command.
- **Force refresh on startup:** `get_ai_manager()` triggers a one-time refresh in background after construction (do not block startup).

### 3.4 Vision Model Discovery

`app/tools/multimodal.py` `vision_models` (lines 29–36) is the worst offender — it duplicates model names that are **already** in `chutes.available_models` / `openrouter.available_models`. After refactor:

```python
# pseudo-code — NOT to be written yet
VISION_NAME_HINTS = ("vl", "vision", "kimi-k2.5", "gemma-3-12b", "gemma-3n")

async def get_vision_models_async(self, provider: str) -> list[str]:
    all_models = await ai_manager.get_provider_models(provider)
    return [m for m in all_models if any(h in m.lower() for h in VISION_NAME_HINTS)]
```

This **decouples** vision from the hardcoded dict. Some providers (OpenRouter) return a `modalities` field on `models.list()` — use it when present, fall back to name heuristics otherwise.

### 3.5 UI / CLI Exposure

The frontend already consumes `models_by_provider` from `/api/config` (`static/js/config.js:427, 461`). The schema does not change — only the source becomes dynamic.

For CLI, expose:
- `python scripts/yuzu_cli.py --list-models` — list cached + fresh-fetched models per provider.
- The existing terminal `/model <provider>/<model>` command (verify it exists; otherwise add) reads from the same dynamic list.

### 3.6 Validation / Allow-list Semantics

The current code uses `model not in self.available_models` to **reject** unknown models before sending. With dynamic lists this becomes a soft-check:

- **Default mode (open):** accept any model returned by the provider.
- **Strict mode (opt-in):** env var `YUZU_STRICT_MODEL_ALLOWLIST=1` → reject models not in the cached list (preserves today's "we know what's supported" guarantee).
- For now: default to **open** with a log warning when the model is not in the cache.

---

## 4. Strategy: Convert Custom Tool Definitions to OpenAI `tools[]` JSON Schema

**This is already 90% done.** The refactor is mostly a verification + cleanup pass.

### 4.1 Current State

`app/tools/schemas.py` lines 1–50 already define `ToolDefinition` + `ToolParam` and emit exactly the OpenAI shape via `to_llm_schema()`. Every tool module (`image_generate.py:21`, `image_edit.py:21`, `http_request.py:22`, `memory_search.py:11`, `memory_store.py:14`, `ask_rei.py:24`, `python_exec.py:54`, `db_query.py`, `shell_exec.py`, `fs_operations.py:28–118`) already uses this. The registry (`registry.py:181`) returns the array via `get_tool_definitions()`.

### 4.2 Required Changes

1. **Add JSON Schema edge cases** to `to_llm_schema()`:
   - `format` for known string formats (`uri`, `path`, `multiline`) — optional, defer to a follow-up if not strictly required.
   - `additionalProperties: False` on the parameters object — OpenAI best practice.
   - `strict: True` on the function object — enables OpenAI's strict mode.
2. **Audit each `ToolParam`** for correct `type`:
   - `image_generate`, `image_edit`, `http_request`, `bash`, `python`, `sql`, `read`, `write`, `ls`, `mkdir`, `rm`, `ask_rei`, `memory_search`, `memory_store` — all currently `type="string"`. Acceptable. Some could become `"object"` for the multi-arg cases (`write`: `{path, content}`, `image_edit`: `{prompt, ...}`), but the current `string` approach is fine for v1.
3. **Standardize `description` quality** — every `ToolParam` must have a one-line `description` that the model reads. (Spot-check: all current ones are present and well-formed.)
4. **No new parser code** — the goal is to *remove* `app/commands.py`'s argument splitter. After refactor, the model emits JSON arguments natively; we just `json.loads(tc.function.arguments)` and pass the dict straight to `execute_tool(name, args, session_id)`.

### 4.3 Alias Resolution

Currently `_TOOL_ALIASES` in `app/commands.py:42–49` maps `imagine` → `image_generate` and `request` → `http_request`. After refactor:

- Either (a) register multiple `TOOL_DEFINITION` entries under the same function name, or
- (b) keep an alias map in `app/tools/registry.py` that resolves `tc.function.name` to the canonical name **before** dispatch.

Recommend (b) — centralize in registry, mirror current behavior.

---

## 5. Strategy: Orchestrator Interception of Native `tool_calls`

### 5.1 Streaming Path (the hard part)

Today, streaming only delivers `content` chunks. We must:

1. Switch `provider.chat_stream()` to use `AsyncOpenAI`'s `chat.completions.create(..., stream=True)`. The SDK yields `ChatCompletionChunk` objects; each chunk has `choices[0].delta` with either:
   - `content` (text) — stream to UI immediately.
   - `tool_calls` (list of `ChoiceDeltaToolCall`) — **accumulate** into a per-call `tool_call` buffer.

2. Buffer pattern (pseudo-code, NOT to be written yet):

```python
class ToolCallBuffer:
    id: str
    name: str
    arguments: str  # streamed as JSON fragment-by-fragment

async def _drain_stream(iterator) -> tuple[str, list[ToolCallBuffer]]:
    text_chunks: list[str] = []
    tcs: dict[int, ToolCallBuffer] = {}
    async for chunk in iterator:
        for choice in chunk.choices:
            if choice.delta.content:
                text_chunks.append(choice.delta.content)
                yield choice.delta.content  # forward to SSE
            for tc_delta in (choice.delta.tool_calls or []):
                idx = tc_delta.index
                buf = tcs.setdefault(idx, ToolCallBuffer(id="", name="", arguments=""))
                if tc_delta.id:
                    buf.id = tc_delta.id
                if tc_delta.function and tc_delta.function.name:
                    buf.name += tc_delta.function.name
                if tc_delta.function and tc_delta.function.arguments:
                    buf.arguments += tc_delta.function.arguments
    return text_chunks, list(tcs.values())
```

3. After stream ends, parse each buffer's `arguments` (JSON) and dispatch via `execute_tool()`.

4. **Persist the assistant turn correctly:** this is the trickiest part. The DB has no `tool_call_id` column on `messages`. For now, persist:
   - One `assistant` message with the streamed text.
   - One `tool` message (or `system_observation` if we keep it) per executed tool, using the same `role` from `get_tool_role()`.

5. **Stitch into next call:** before the next LLM call (e.g. synthesis pass), append SDK-shaped messages to `ephemeral_context`:
   ```python
   [
       {"role": "assistant", "content": text, "tool_calls": [...]},
       {"role": "tool", "tool_call_id": tc.id, "content": markdown},
   ]
   ```

### 5.2 Non-Streaming Path (`handle_user_message`)

`orchestrator._parse_raw_tool_calls_async` (line 217) and `_execute_tool_calls_async` (line 240) **already exist** and mostly do the right thing. Required updates:

- `provider.parse_tool_calls(raw)` (only implemented in `openrouter.py:212`) → replace with a **base implementation** in `base.py` that reads `raw.choices[0].message.tool_calls` directly. Since all four providers will use the same SDK shape, the per-provider override can be deleted.
- After tool execution, build the `ephemeral_context` with `tool` role messages and `tool_call_id`s — see §5.1 step 5.

### 5.3 Synthesis Pass

The current `ephemeral_context` is:
```python
[{"role": "assistant", "content": full_response},
 {"role": "user",      "content": tool_markdown}]
```

It needs to become:
```python
[{"role": "assistant", "content": full_response, "tool_calls": [...]},
 {"role": "tool", "tool_call_id": tc.id, "content": tool_markdown}]
```

The model now sees proper tool-call structure, not "user speaking the tool result." This is the entire point of moving to native `tool_calls`.

### 5.4 Orchestration Loop

`_run_orchestration_loop_async` (line 492) currently loops on `parse_tool_blocks(synthesis)`. Replace with:

```python
# pseudo-code
synthesis_text, raw = await _send_to_provider(...)  # now returns ChatCompletion
if raw.choices[0].message.tool_calls:
    # more tool calls — execute, stitch, loop
else:
    # done
    break
```

The current 30-iteration cap (`_MAX_ORCHESTRATION_LOOPS`) is preserved.

### 5.5 Backwards Compatibility (transitional)

If we want to ship the refactor incrementally:

1. **Phase 2a:** Migrate HTTP → SDK. Keep `<command>` parser as fallback. Provider emits `<command>` for tools not yet in OpenAI `tools[]` format (none currently — all tools are already in `tools[]`).
2. **Phase 2b:** Wire `tools=schemas` in `chat_complete` / `chat_stream`. Orchestrator inspects `raw.choices[0].message.tool_calls` first; falls back to `<command>` parsing if empty.
3. **Phase 2c:** After verified, drop `<command>` parser. Update system prompt.

The user's "ACC" gates each phase. Recommended: **ship 2a+2b together** (since `to_llm_schema()` is already in place), then 2c as a small follow-up commit.

---

## 6. Open Questions / Risks

1. **Model-streaming + tool_calls interaction on providers that don't stream `tool_calls` deltas** (e.g. older Chutes routes). Mitigation: detect via `len(raw.choices[0].message.tool_calls or []) > 0` post-stream, and re-issue a non-streaming call to recover the tool_calls if deltas were lost.
2. **Ollama `/v1/models` may not exist on very old versions.** Detect version via a `GET /api/version` probe; if `/v1/models` is missing, fall back to a small allow-list per major Ollama version.
3. **DB schema for tool_call_id.** The current `messages` table has no `tool_call_id` column. Two options: (a) add a column (DB migration — adds a column only, per `AGENTS.md` rules); (b) embed `tool_call_id` in the `tool` role's `content` as a header. Option (b) is non-disruptive; option (a) is cleaner. Recommend (b) for v1.
4. **Front-end streaming.** `static/js/chat.js` already renders delta content; it does **not** currently render `tool_call` events (there are none). After refactor, the back-end will persist tool calls as separate `tool` role messages in the DB, which the chat UI already renders. **No front-end change required.**
5. **Token cost.** The `<command>` parser is line-start-anchored and strips tool blocks before sending to the UI, but the **model still has to emit them** — so there's no token cost change in that direction. The new `tools` array is sent on every request; the cost is comparable.
6. **Prompt size.** `_get_relevant_tools()` in `prompts.py:298–365` injects `<command>` examples only when contextually relevant. After refactor, this whole function should be replaced with a similar "include only relevant tool descriptions in the system prompt" — but the source is now `ToolDefinition.description` not a hand-written string. This is a follow-up optimization, not a blocker.

---

## 7. Execution Plan (Pending ACC)

If approved, the execution will be split into the following commits on a feature branch (not `master`):

1. **`feat/openai-sdk-dep`** — add `openai>=1.50.0` to `requirements.txt` + `pyproject.toml`. Verify `pip install -r requirements.txt` succeeds.
2. **`refactor/providers-base`** — extract rate-limit into its own module; convert `AIProvider` to a thin SDK wrapper; add `chat_complete` / `chat_stream` / `chat_text` abstract methods. **No provider behavior change yet.**
3. **`refactor/chutes-sdk`** — migrate Chutes first (most-used, has the fallback-loop logic); keep `<command>` parser untouched; verify streaming + retry behavior with `ruff` + smoke test.
4. **`refactor/{openrouter,cerebras,ollama}-sdk`** — one provider per commit, same pattern.
5. **`feat/dynamic-model-cache`** — add `_fetch_models_cached()` to base; wire `get_all_models` to use it; remove `available_models` lists from each provider.
6. **`feat/dynamic-vision-models`** — replace `multimodal.vision_models` dict with `/v1/models` + heuristics.
7. **`feat/native-tool-calls`** — add SDK-shaped message conversion in `orchestrator`; keep `<command>` parser as fallback path. Update system prompt to mention native tools but keep `<command>` examples.
8. **`refactor/remove-command-parser`** — once verified, delete `parse_tool_blocks` / `execute_commands`; rewrite system-prompt tool docs.
9. **`chore/tests-update`** — replace `<command>` parser tests with SDK `tool_calls` parser tests.
10. **`docs/update-agents-md`** — update `AGENTS.md` §4 and §8 to reflect native `tools[]` protocol.

Each commit includes `ruff check .` and `python3 -m py_compile` on changed files. Each commit is **rolled back** on any regression rather than patched forward.

---

## 8. Out of Scope (for this refactor)

- Replacing the `requests` usage in `image_generate.py`, `image_edit.py`, `http_request.py`, `ask_rei.py` (image generation/edit/HTTP tools have their own non-LLM endpoints and stay on `httpx`).
- Replacing `httpx` in `app/memory/embedder.py` (Chutes embedding API can also use `AsyncOpenAI`, but is a separate concern).
- UI/UX changes — none required.
- DB schema migration — none required (option (b) for `tool_call_id`).
- Vision auto-routing logic in `llm_client._send_to_provider` (line 220–238) — keep as-is; just the model list becomes dynamic.

---

**End of Phase 1 audit.** Awaiting "ACC" to proceed.
roviders/cerebras.py` | 16–28, 30–32 | Same. |
| `app/providers/ollama.py` | 14–28, 30–32 | Same — uses `AsyncOpenAI(base_url=f"{base_url}/v1").models.list()`. |
| `app/providers/base.py` | 322–344 | `AIProviderManager.get_all_models()` (already async) — wrap each provider's dynamic `get_models()` with a TTL cache (see §3). |
| `app/services/config_service.py` | 25–75 | Replace hand-curated `vision_models_by_provider` with: query each provider's `/v1/models`, intersect with a "supports vision" heuristic (provider-specific metadata or capability table). |
| `app/tools/multimodal.py` | 29–36, 546–615 | Delete `self.vision_models` hardcoded dict. Refactor `get_available_vision_models()` to call `provider.get_models()` and filter by provider-declared tags (e.g., Ollama model `:cloud` family, OpenRouter's `qwen3-vl`/`gemini-flash` patterns). `get_best_vision_provider()` keeps the priority logic but sources models dynamically. |
| `app/api/endpoints/profile.py` | 60–90, 188–210 | The `/api/config` payload already returns `models_by_provider` and `current_provider`/`current_model` — no schema change needed, but the data now comes from live `/v1/models`. |

### 1.6 Tool Schemas (Already Mostly Compliant)

| File | Lines | Required Change |
|---|---|---|
| `app/tools/schemas.py` | 1–218 | **Minor.** `ToolParam.type` (line 16) is a freeform string. Tighten to a `Literal["string","number","boolean","object","array"]` for type safety. `to_llm_schema()` already produces the correct format — verify it produces `additionalProperties: false` and a `required` array (currently it adds `required` correctly). |
| `app/tools/image_generate.py`, `image_edit.py`, `memory_store.py`, `memory_search.py`, `http_request.py`, `python_exec.py`, `shell_exec.py`, `db_query.py`, `ask_rei.py`, `fs_operations.py` | — | **No structural change.** All ten tools already expose a `TOOL_DEFINITION` dataclass whose `to_llm_schema()` is OpenAI-compatible. Verify each has a strict JSON Schema (no missing `description`, no missing `required` markers). |
| `app/tools/__init__.py` | 1–24 | No change. |
| `app/tools/multimodal.py` (image gen + vision) | entire file | The vision/image generation helpers are **not in the LLM `tools[]` array** — they're called by `MultimodalTools` directly. After refactor, vision routing should consume `provider.supports_vision()` from the SDK's `model.metadata` rather than the local `vision_models` dict. |

### 1.7 New Files

| File | Purpose |
|---|---|
| `app/providers/rate_limit.py` | Extract `_rate_limit_provider`, `_get_provider_semaphore_async`, `_get_model_semaphore_async`, `_retry_with_backoff` from `base.py:25–177` so the new SDK wrappers don't carry the legacy lock machinery. |
| `app/providers/openai_base.py` | Provide `OpenAICompatibleProvider` mixin that owns `self._client: openai.AsyncOpenAI`, `base_url`, `api_key`, and the four methods (`chat_complete`, `chat_stream`, `get_models`, `parse_tool_calls`). All four concrete providers become 30-line subclasses that just declare `base_url` and any non-standard headers. |

---

## 2. Strategy: HTTP → `AsyncOpenAI`

### 2.1 SDK Initialization

Each provider subclass sets `base_url` and (where applicable) provider-specific headers in `__init__`:

```python
self._client = openai.AsyncOpenAI(
    base_url=base_url,
    api_key=api_key or "no-key",   # SDK requires non-empty; choke-later
    default_headers=extra_headers, # OpenRouter's HTTP-Referer/X-Title, etc.
    timeout=180.0,
    max_retries=0,                 # We own the retry policy
)
```

`api_key` is loaded **lazily** via `await get_api_key_async(self.name)` in `AIProvider.initialize()` (already async, `base.py:200–205`).

### 2.2 Chat Completion

Replace `httpx.AsyncClient.post(self.base_url, json=payload, headers=headers, timeout=...)` with:

```python
response = await self._client.chat.completions.create(
    model=model,
    messages=messages,
    temperature=kwargs.get("temperature", 0.7),
    max_tokens=kwargs.get("max_tokens") or None,
    top_p=kwargs.get("top_p", 0.9),
    stream=False,
    tools=kwargs.get("tools") or NOT_GIVEN,
    tool_choice="auto" if kwargs.get("tools") else NOT_GIVEN,
)
```

The SDK returns an `openai.types.chat.ChatCompletion` — and `message.content` / `message.tool_calls` / `message.role` are all Pydantic-typed, so schema migrations of upstream providers are handled for free.

### 2.3 Streaming

Replace the `httpx.AsyncClient().stream("POST", ...)` + manual SSE parsing:

```python
async with self._client.chat.completions.create(
    model=model,
    messages=messages,
    stream=True,
    tools=tools,
    tool_choice="auto",
) as stream:
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
        # tool_call_delta is exposed on chunk.choices[0].delta.tool_calls
```

Caveat: the current orchestrator streams **only content** to the UI. The SDK separates content deltas and tool-call deltas. The refactor must yield content as before but **accumulate** tool-call deltas locally, execute them once `finish_reason == "tool_calls"`, and yield the results as a new round (insertion into `ephemeral_context`). See §4.

### 2.4 Cancellation

The existing code raises `asyncio.CancelledError` in the streaming block (`llm_client.py:381–390`, `chutes.py:241`). The SDK already propagates cancellation through `httpx` cleanly — keep the existing exception-propagation, just remove the manual `except httpx.RequestError` paths.

### 2.5 Retry / Rate Limiting

The `_rate_limit_provider` async-context-manager (`base.py:79–177`) and `_retry_with_backoff` (base.py:179–238) stay — they sit **above** the SDK call:

```python
async with _rate_limit_provider(self.name, model, source):
    response = await self._client.chat.completions.create(...)
```

This preserves the per-provider/per-model semaphore binding to the current event loop (the cross-loop bug fix from `base.py:48–75`).

---

## 3. Architecture: Dynamic Model Discovery (`/v1/models`)

### 3.1 Provider Contract

Each provider implements:

```python
async def get_models(self) -> list[str]:
    response = await self._client.models.list()
    return sorted(m.id for m in response.data)
```

The `openai.AsyncOpenAI.models.list()` API returns one or more pages; the SDK auto-paginates via `async iter`. Providers must cache the result.

### 3.2 Cache Strategy

| Layer | Where | TTL | Refresh |
|---|---|---|---|
| Process-wide LRU | `AIProviderManager._models_cache: dict[(provider, hash(api_key)), tuple[float, list[str]]]` | **15 minutes** | Lazy on TTL expiry |
| Per-provider extra | None needed initially; revisit if any provider exposes hundreds of models | — | — |
| Persisted | `api_settings` table (already exists in `app/db/facade.py`) stores `cached_models_json` per provider | **24 hours** | On startup, hydrate cache from DB; refresh on TTL expiry; on TTL expiry + failed `/v1/models` call, fall back to DB cache |

Rationale for two-tier cache:
- **15-minute in-process** handles the 30-message/min burst of `ConfigService.get_frontend_config()` being polled by the web UI on every page load.
- **24-hour persisted** keeps the provider picker usable even when the upstream API is down.

### 3.3 UI / CLI Exposure

| Surface | Today | After refactor |
|---|---|---|
| Web `/api/config` → `vision.models_by_provider` | Hardcoded `vision_models` dict (`config_service.py:64–73`) | `await asyncio.gather(*[p.get_models() for p in providers])` then filter by `provider.is_vision_model(name)` capability. |
| Web `/api/config` → `ai_providers.all_models` | `ai_manager.get_all_models()` already in place (`llm_client.py:208–222`) | Now served from cache; stale data carries a `cached_at: float` watermark so the frontend badge can say "models refreshed 12 min ago". |
| CLI (`scripts/yuzu_cli.py`, `cli/app.py`) | Already uses the same `ConfigService.get_frontend_config()` pipeline | No change. |
| Frontend `static/js/config.js:427, 461` | Reads `visionConfig.models_by_provider` | Refresh after `setInterval(15min)` to pick up newly-added upstream models without a page reload. |

### 3.4 Vision-Capability Filter

The hardcoded `self.vision_models` dict in `multimodal.py:29–36` must be deleted. The replacement capability check should:
1. Try the SDK's `models.retrieve(model_id)` per model and inspect `metadata["supports_vision"]` or similar (provider-specific).
2. Fall back to a small **maintainer-maintained pattern dict** (`{"qwen*-vl*": True, "kimi-k2.*": True, "gemma-*-31B": True, "gemini-flash*": True, ...}`) keyed on prefix match — same heuristic strength as today's hardcoded list, but updated per release.
3. Provide `is_vision_model(model_name, provider)` in a new `app/providers/capabilities.py` module.

---

## 4. Strategy: Standardizing Tools as Native OpenAI JSON Schema

### 4.1 Schema Is Already Correct

`ToolDefinition.to_llm_schema()` (`schemas.py:28–51`) already produces the exact format the OpenAI SDK wants. Required adjustments:

| Field | Today | After refactor |
|---|---|---|
| `type` | always `"function"` ✓ | unchanged |
| `additionalProperties` | missing | add `"additionalProperties": False` |
| `parameters.type` | always `"object"` ✓ | unchanged |
| `properties.<name>.type` | supports 5 types but no `"integer"` | add `integer` and `null` |
| `description` per param | present ✓ | unchanged |
| `required` array | correctly populated | unchanged |
| `enum` per param | already wired | keep |

### 4.2 Drop the `<command>` Parser Entirely

Today's parser (`commands.py:95–219`) handles:
- `<command>` line-start detection via custom string-split (avoiding ReDoS).
- `imagine` → text → `_STRING_ARG_TOOLS["imagine"] = "prompt"` mapping.
- `request GET <url>` → split on whitespace → `{url}`.
- `read path → {path}`.
- `image_edit` with multi-arg `key=value; key2="value with spaces"`.
- Aliases `ask-rei` → `ask_rei`, `request` → `http_request`.

After the refactor, all of this is replaced by the SDK's native tool-calling pipeline:
- `ToolCall.function.name` becomes `tool_name` (server-side alias resolution in `registry.execute_tool()`).
- `ToolCall.function.arguments` arrives as a JSON string (or dict, depending on SDK version) → parse with `json.loads()` once, never re-validate.
- `tool_name=ask_rei` with `{"message": "..."}` arrives directly; no string split needed.
- `tool_name=read` with `{"path": "..."}` arrives directly.

### 4.3 Single-Mode Protocol

After refactor, **all tool dispatch flows through native `tool_calls`**. The old paths to remove:

| Path | Location | Action |
|---|---|---|
| `<command>` block parser | `commands.py:95–219` | DELETE |
| `_parse_command_string`, `_parse_args`, `_parse_key_value_args` | `commands.py:241–340` | DELETE |
| `execute_commands` | `commands.py:480–525` | DELETE — replaced by native `tool_calls` execution. |
| `/imagine` fast-path branch | `orchestrator.py:648–660` | DELETE — relies on stripped command syntax. |
| `StreamFilter` class (already removed) | n/a | confirmed already gone |
| `_STRING_ARG_TOOLS`, `_TOOL_ALIASES` dicts | `commands.py:31–51` | REPLACE with a single `dict[str, str]` alias map kept in `registry.py` for `name -> canonical_name`. |

### 4.4 Backwards Compatibility Caution

If user-visible commands typed directly (`/imagine ...`) must still work as keyboard shortcuts, keep `parse_tool_blocks` as a **parser for raw user input only**, scoped to `handle_user_message`'s pre-LLM fastpath. **However** — the AGENTS.md says v3.1.0 removed legacy `/command` syntax. The fastpath at `orchestrator.py:648` should also be deleted for consistency. Decide before execution and document the breaking-change in CHANGELOG.

---

## 5. Strategy: Orchestrator Intercepts Native `tool_calls`

### 5.1 Streaming Flow (Async Iterator)

```
[user msg] → llm_client._send_to_provider(provider.chat_stream(messages, tools=schemas))
            → AsyncOpenAI stream
            ↓
[fn _iter_stream_with_tool_calls(stream)]
   - yield chunk.choices[0].delta.content             → UI renderer
   - accumulate chunk.choices[0].delta.tool_calls      → local tool_call buffer
   - when finish_reason == "tool_calls":
       1.   resolve aliases in registry
       2.   execute_tool(name, json.loads(arguments))
       3.   inject tool result back:
              ephemeral_context.append({
                  "role":       "tool",
                  "tool_call_id": tc.id,
                  "content":     json.dumps(result),
              })
              ephemeral_context.append({
                  "role":       "assistant",  # prior turn's tool_call message
                  "tool_calls": [tc.model_dump()],
              })
       4.   recurse: open a NEW SDK stream with messages = build_messages() + ephemeral_context
       5.   continue yielding chunks
```

The above collapses into a single async generator. The orchestrator's stitching today (`format_observation` → ephemeral_context) becomes unnecessary because the SDK's `tool` role message has a fixed shape.

### 5.2 Non-Streaming Flow

```
[user msg] → llm_client.generate_ai_response
            → provider.chat_complete(messages, tools=schemas)
            → ChatCompletion(message.tool_calls=...)
            ↓
[fn _handle_native_tool_calls(message.tool_calls)]
   - convert each ToolCall → dict{id, name, arguments}
   - await execute_tool(name, arguments) for each, sequential
   - if any tool.is_terminal and result.ok → finalize, skip synthesis
   - else: build ephemeral_context, recurse: provider.chat_complete(
                                       messages + ephemeral_context,
                                       tools=schemas)
   - loop until message.tool_calls is empty or _MAX_ORCHESTRATION_LOOPS hit
```

### 5.3 Result-to-Tool-Message Bridge

`execute_tool()` returns `{"ok", "data", "markdown"}` or `{"ok": False, "error", "markdown"}`. The orchestrator must convert that into the `{"role": "tool", "tool_call_id": ..., "content": ...}` SDK message. Recommendation:

```python
{
    "role": "tool",
    "tool_call_id": tc.id,
    "content": json.dumps({
        "ok": result["ok"],
        "data": result.get("data", {}),
        "markdown": result.get("markdown"),  # for SSOT DB persistence
        "error": result.get("error"),
    }),
}
```

The `markdown` field is preserved in DB (via `_persist_tool_result_async`) but is **also** passed back to the LLM as JSON content so the LLM can summarize for the user.

### 5.4 Termination Conditions

| Today (`_run_orchestration_loop_async`) | After refactor |
|---|---|
| `parse_tool_blocks(synthesis)` | `if response.choices[0].finish_reason != "tool_calls": break` |
| `if not synthesis: return` | `if not response.choices[0].message.content: continue` |
| `_MAX_ORCHESTRATION_LOOPS = 30` (orchestrator.py:24) | keep, but the limiter now wraps **SDK round-trips**, not parser loops |
| `len(has_tool_blocks(synthesis) and next_commands)` check | replaced by SDK's native finish_reason signal |

---

## 6. Risk & Migration Order

### 6.1 Risk Inventory

| Risk | Severity | Mitigation |
|---|---|---|
| **Provider behavior drift** — SDK may differ in streaming chunk format vs. today's hand-rolled SSE parser | Medium | Phase the refactor per provider: chutes → openrouter → cerebras → ollama. Each phase ends with a regression test. |
| **`<command>` parser removal breaks user muscle memory** in the prompt | Medium | Keep `parse_tool_blocks` for **direct user input** (the `/imagine foo` keyboard shortcut). Treat LLM-protocol and user-input-protocol as two separate things. |
| **Tool-call IDs are required by SDK** (`tool_call_id` in `tool` role message) | High | Make sure every `ToolCall` we send back has its matching ID. The SDK ensures this; the orchestrator must preserve it through `ephemeral_context`. |
| **Vision models dynamic list might omit models the user already configured** | High | On startup, persist the user's previously-saved `vision_model_preferences` and only fall back if dynamic discovery fails. Keep a 24h DB cache. |
| **`openai` SDK adds dependency** | Low | `openai>=1.40.0` is the recommended version (long-term stable, async-first). Update `requirements.txt` and `pyproject.toml` together. |
| **Streaming cancellation propagation changes** | Low | The SDK propagates `asyncio.CancelledError` through `httpx`. Today's explicit re-raise in `chutes.py:241` can be removed since the SDK does it. |

### 6.2 Suggested Execution Phases (After ACC)

1. **Phase A — Foundation**
   - Add `openai>=1.40` to `requirements.txt` and `pyproject.toml`.
   - Create `app/providers/rate_limit.py` (extract from `base.py`).
   - Create `app/providers/openai_base.py` (the SDK mixin).
   - Write unit tests that mount a fake HTTP server returning `/v1/models` and `chat/completions` payloads → verify `get_models()` and `chat_complete()` against the SDK.

2. **Phase B — Chutes provider (highest volume)**
   - Migrate `chutes.py` to use `openai_base.py`.
   - Replace hardcoded `available_models`.
   - Verify with `tests/test_commands.py`-style checks against a recorded Chutes response.

3. **Phase C — OpenRouter + Cerebras**
   - OpenRouter preserves `HTTP-Referer`/`X-Title` via `default_headers`.
   - Cerebras is a straight port.

4. **Phase D — Ollama**
   - Handle `/v1/models` availability per Ollama version (≥0.3.x required).

5. **Phase E — Tool protocol switch**
   - Update orchestrator to intercept `tool_calls`.
   - Delete `<command>` parser from `commands.py`.
   - Rewrite `prompts.py` tool docs.

6. **Phase F — Dynamic models for vision/image-generation**
   - Refactor `multimodal.py` capability detection.
   - Wire 15-min in-process + 24h DB cache.

7. **Phase G — Verification**
   - Run `ruff check .` and `python3 -m py_compile` on each modified file.
   - Run full test suite (`python3 -m pytest tests/`).
   - Spin up a real provider with `--provider chutes --model ...` and confirm `tool_calls` round-trip end-to-end.

### 6.3 Rollback Plan

Each phase lands on its own feature branch (`feat/sdk-chutes`, `feat/sdk-openrouter`, …). If a phase introduces a regression, `git revert <merge>` + delete the branch. The pre-refactor commits stay reachable for fast rollback.

---

## 7. Acceptance Criteria

When the refactor is approved and executed:

- [ ] `requirements.txt` and `pyproject.toml` declare `openai>=1.40`.
- [ ] All four providers run their chat calls through `openai.AsyncOpenAI`.
- [ ] No file under `app/providers/` imports `httpx` or `requests` for chat completions (image generation / image downloading may still use them, since those hit different endpoints).
- [ ] All four providers expose a `get_models()` backed by the SDK's `models.list()`, with a 15-minute in-process cache.
- [ ] `app/commands.py` no longer exports `parse_tool_blocks`, `has_tool_blocks`, `_parse_args`, `_parse_key_value_args`, or `execute_commands` for LLM-side dispatch. Direct user input handling may keep these scoped narrowly.
- [ ] `app/prompts.py` no longer instructs the model to emit `<command>` blocks.
- [ ] `app/orchestrator.py` `handle_user_message` and `handle_user_message_streaming` route through `provider.chat_complete` / `provider.chat_stream` and intercept `tool_calls` natively.
- [ ] `app/tools/schemas.py.ToolDefinition.to_llm_schema()` includes `additionalProperties: false` and supports `integer`/`null` parameter types.
- [ ] `app/tools/multimodal.py` no longer hardcodes `self.vision_models`.
- [ ] Web `/api/config` shape unchanged (frontend compatibility preserved).
- [ ] Existing tests in `tests/test_commands.py`, `tests/test_prompts.py`, and `tests/test_memory.py` pass after updates.
- [ ] `ruff check .` and `python3 -m py_compile` pass.

---

## 8. What Is NOT Changing

To keep the blast radius explicit:

- **Tool execution surface** (`tools/registry.py:execute_tool`) stays the single dispatch point. Only its **callers** change.
- **Database schema** stays untouched (no schema migration needed).
- **Memory pipeline** (`app/memory/*`) stays untouched.
- **Streaming pipeline** (`app/stream_manager.py`) stays untouched. Only the chunks it relays change shape (still text + tool-marker events, just sourced from SDK).
- **Frontend** stays untouched (`static/js/*`). The `/api/config` payload and the SSE event shapes are preserved.
- The `<tools>...</tools>` markdown contract (rendered for the user and persisted in DB) stays — only the **way** we produce that markdown from the LLM response changes (native `tool_calls` instead of `<command>` blocks).

---

*End of Phase 1 Plan. Awaiting "ACC" before any code changes.*
