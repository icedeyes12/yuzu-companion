# 🏗️ Provider & Tooling Refactor Plan — Phase 1 Audit

> **Status:** AWAITING APPROVAL — Do not generate code until user sends `ACC`
> **Date:** 2026-06-16
> **Branch:** `dev`
> **Scope:** Provider SDK migration, interface redesign, native tool calling
> **Previous plan:** `REFACTOR_PLAN.md` (superseded — that plan lacked the interface audit detail needed to avoid the kwargs-dropping bug)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Audit Results](#2-audit-results)
3. [New Base Provider Interface](#3-new-base-provider-interface)
4. [Per-Provider Migration Plan](#4-per-provider-migration-plan)
5. [Orchestrator Migration Plan](#5-orchestrator-migration-plan)
6. [Tool Schema Migration Plan](#6-tool-schema-migration-plan)
7. [Stream Manager Changes](#7-stream-manager-changes)
8. [Step-by-Step Execution Order](#8-step-by-step-execution-order)
9. [Files Modified per Step](#9-files-modified-per-step)
10. [Risk Matrix](#10-risk-matrix)
11. [Appendix: Full Call Site Map](#appendix-full-call-site-map)

---

## 1. Problem Statement

### 1.1 The kwargs-Dropping Bug

Every provider accepts `**kwargs` in `send_message*()` methods but **none** forward them into the HTTP payload:

```python
# What the caller expects:
await provider.send_message(messages, model, tools=tool_schemas)

# What actually happens inside every provider:
payload = {"model": model, "messages": messages, "max_tokens": 8192, "temperature": 0.7}
# ^^^ tools= silently dropped — never added to payload
```

| Provider | `send_message` | `send_message_raw` | `send_message_streaming` |
|---|---|---|---|
| Chutes | ❌ kwargs dropped | ❌ kwargs dropped | ❌ kwargs dropped |
| OpenRouter | ❌ kwargs dropped | ❌ kwargs dropped | ❌ kwargs dropped |
| Cerebras | ❌ kwargs dropped | Uses base (wraps `send_message`) | ❌ kwargs dropped |
| Ollama | ❌ kwargs dropped | Uses base (wraps `send_message`) | ❌ kwargs dropped |

### 1.2 Why Patching Won't Work

The legacy `send_message → str` contract is fundamentally incompatible with tool calling:

- `send_message()` returns `str` — tool calls live in `message.tool_calls`, not in content
- `send_message_raw()` wraps `send_message` output in a fake response dict — structured tool call data is lost
- `send_message_streaming()` yields `str` chunks — `tool_call_delta` chunks have no content path

**The interface itself must be replaced**, not patched.

### 1.3 Additional Problems

- **No `openai` SDK usage** — All 4 providers use raw `httpx` with manual SSE parsing (~400 lines of duplicated code)
- **Hardcoded model lists** — 3 of 4 providers return hardcoded model lists (only Ollama fetches dynamically)
- **Text-based tool parsing** — The orchestrator parses `<tool>` blocks from LLM text output via regex, missing native function calling entirely
- **OpenAI schemas exist but are orphaned** — `app/tools/schemas.py` already has complete OpenAI-format tool schemas but nothing uses them

---

## 2. Audit Results

### 2.1 Provider Architecture (Current)

```
AIProvider (abstract)
├── send_message(messages, model, **kwargs) → str          [ABSTRACT]
├── send_message_streaming(messages, model, **kwargs) → AsyncGenerator[str]  [ABSTRACT]
├── send_message_raw(messages, model, **kwargs) → dict     [DEFAULT: wraps send_message]
├── get_available_models() → list[str]                     [DEFAULT: returns []]
├── get_model_display_name(model_id) → str
├── get_current_model() → str
├── set_model(model) → None
├── get_name() → str
├── get_api_key() → str
├── get_base_url() → str
└── _get_default_model() → str

ChutesProvider(AIProvider)      — base_url: https://chutes.ai/api/v0
OpenRouterProvider(AIProvider)  — base_url: https://openrouter.ai/api/v1
CerebrasProvider(AIProvider)    — base_url: https://api.cerebras.ai/v1
OllamaProvider(AIProvider)      — base_url: http://localhost:11434
```

### 2.2 LLM Client Functions (Current)

| Function | Location | What It Calls | Returns |
|---|---|---|---|
| `generate_ai_response()` | `llm_client.py:89` | `provider.send_message_raw()` or `.send_message()` | `str` |
| `generate_ai_response_with_context()` | `llm_client.py:185` | `generate_ai_response()` via `build_message_context()` | `str` |
| `generate_ai_response_streaming()` | `llm_client.py:269` | `provider.send_message_streaming()` | `AsyncGenerator[str]` |
| `generate_ai_response_streaming_with_context()` | `llm_client.py:311` | `generate_ai_response_streaming()` via `build_message_context()` | `AsyncGenerator[str]` |
| `chutes_chat()` | `llm_client.py:232` | `provider.send_message()` (Chutes only) | `str` |

### 2.3 Orchestrator Call Sites

| Location | Function Called | Purpose |
|---|---|---|
| `orchestrator.py:224` | `generate_ai_response_with_context()` | Primary LLM call (non-streaming) |
| `orchestrator.py:370` | `generate_ai_response()` | Synthesis pass (non-streaming) |
| `orchestrator.py:489` | `generate_ai_response_streaming_with_context()` | Primary LLM call (streaming) |
| `orchestrator.py:618` | `generate_ai_response_streaming()` | Synthesis pass (streaming) |
| `orchestrator.py:239` | `parse_tool_blocks(ai_response)` | Parse `<tool>` blocks from text |
| `orchestrator.py:529` | `parse_tool_blocks(full_response)` | Parse `<tool>` blocks from streamed text |
| `orchestrator.py:264` | `execute_tool(name, arguments, session_id)` | Execute individual tool |
| `orchestrator.py:555` | `execute_tool(name, arguments, session_id)` | Execute individual tool (streaming) |

### 2.4 Direct `provider.send_message()` Call Sites (Outside LLM Client)

These bypass `llm_client.py` and call the provider directly:

| Location | Purpose |
|---|---|
| `memory/memory_review.py:36` | Memory review LLM call |
| `memory/pcl.py:79` | PCL prediction pass |
| `memory/pcl.py:112` | PCL calibration pass |
| `tools/ask_rei.py:80` | Secondary AI query |
| `tools/db_query.py:95` | SQL generation |
| `tools/db_query.py:122` | SQL explanation |
| `profile_analysis.py:22` | Profile analysis |

### 2.5 `chutes_chat()` Call Sites

| Location | Purpose |
|---|---|
| `memory/memory.py:269` | Memory extraction |
| `memory/memory.py:325` | Conversation segmentation |
| `memory/memory.py:422` | Memory analysis |
| `memory/memory.py:481` | Memory result processing |

### 2.6 Existing OpenAI Schemas (Ready but Orphaned)

`app/tools/schemas.py` already defines complete OpenAI-format schemas for all 10 tools:
`bash`, `python`, `image_generate`, `image_edit`, `http_request`, `memory_search`, `memory_store`, `fs`, `db_query`, `ask_rei`

Functions `get_openai_tools()` and `get_tool_schema()` are defined but **called nowhere**.

---

## 3. New Base Provider Interface

### 3.1 Design Principles

1. **`tools` is a first-class parameter** — not hidden in `**kwargs`
2. **Return types carry structure** — `ChatCompletion` / `ChatCompletionChunk`, not `str`
3. **One SDK client per provider** — `openai.AsyncOpenAI` handles HTTP, SSE, retries
4. **Legacy methods are shims** — they call the new methods internally during transition

### 3.2 New Class Hierarchy

```python
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

class AIProvider(ABC):
    """Abstract base — unchanged identity/config surface."""

    def __init__(self, name: str, api_key: str = "", base_url: str = ""): ...
    def get_name(self) -> str: ...
    def get_api_key(self) -> str: ...
    def get_base_url(self) -> str: ...
    def get_current_model(self) -> str: ...
    def set_model(self, model: str) -> None: ...
    def get_model_display_name(self, model_id: str) -> str: ...
    def _get_default_model(self) -> str: ...

    # --- NEW ABSTRACT INTERFACE ---

    @abstractmethod
    async def chat_complete(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        **kwargs,
    ) -> ChatCompletion: ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        **kwargs,
    ) -> AsyncGenerator[ChatCompletionChunk, None]: ...

    @abstractmethod
    async def get_available_models(self) -> list[str]: ...

    # --- DEPRECATED SHIMS (removed in v4.0) ---

    async def send_message(self, messages, model=None, **kwargs) -> str:
        """DEPRECATED: Use chat_complete() instead."""
        resp = await self.chat_complete(messages, model, **kwargs)
        return resp.choices[0].message.content or ""

    async def send_message_raw(self, messages, model=None, **kwargs) -> dict:
        """DEPRECATED: Use chat_complete() instead."""
        resp = await self.chat_complete(messages, model, **kwargs)
        return resp.model_dump()

    async def send_message_streaming(self, messages, model=None, **kwargs) -> AsyncGenerator[str, None]:
        """DEPRECATED: Use chat_stream() instead."""
        async for chunk in self.chat_stream(messages, model, **kwargs):
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content


class OpenAICompatibleProvider(AIProvider):
    """Concrete base for providers with /v1/chat/completions endpoints."""

    def __init__(self, name: str, api_key: str, base_url: str,
                 default_headers: dict[str, str] | None = None):
        super().__init__(name, api_key, base_url)
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers,
        )

    async def chat_complete(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        **kwargs,
    ) -> ChatCompletion:
        params: dict = {
            "model": model or self.get_current_model(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        if tools:
            params["tools"] = tools
        return await self._client.chat.completions.create(**params)

    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        **kwargs,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        params: dict = {
            "model": model or self.get_current_model(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }
        if tools:
            params["tools"] = tools
        stream = await self._client.chat.completions.create(**params)
        async for chunk in stream:
            yield chunk

    async def get_available_models(self) -> list[str]:
        models = await self._client.models.list()
        return sorted(m.id for m in models.data)
```

### 3.3 Why This Kills the kwargs-Dropping Bug

| Old Pattern | New Pattern |
|---|---|
| `send_message(**kwargs)` → provider builds payload manually, ignores kwargs | `chat_complete(tools=...)` → `tools` is an explicit parameter, forwarded to `self._client.chat.completions.create(tools=tools)` |
| Return `str` → tool calls invisible | Return `ChatCompletion` → `response.choices[0].message.tool_calls` is accessible |
| Stream yields `str` → deltas invisible | Stream yields `ChatCompletionChunk` → `chunk.choices[0].delta.tool_calls` is accessible |

---

## 4. Per-Provider Migration Plan

### 4.1 Chutes → `OpenAICompatibleProvider`

```
Before: ChutesProvider(AIProvider) — raw httpx, base_url https://chutes.ai/api/v0
After:  ChutesProvider(OpenAICompatibleProvider)
```

- **Base URL:** `https://chutes.ai/api/v0` (Chutes exposes OpenAI-compatible `/chat/completions`)
- **Headers:** None special needed
- **Overrides:** None — vanilla `OpenAICompatibleProvider` behavior
- **Model list:** Switch from hardcoded to `self._client.models.list()` (if Chutes supports `/v1/models`; if not, keep hardcoded list as override)
- **Lines deleted:** ~130 lines of manual httpx + SSE parsing

### 4.2 OpenRouter → `OpenAICompatibleProvider`

```
Before: OpenRouterProvider(AIProvider) — raw httpx, base_url https://openrouter.ai/api/v1
After:  OpenRouterProvider(OpenAICompatibleProvider)
```

- **Base URL:** `https://openrouter.ai/api/v1`
- **Headers:** `HTTP-Referer`, `X-Title` via `default_headers`
- **Overrides:** `chat_complete()` and `chat_stream()` must inject `extra_body`:
  ```python
  extra_body = {
      "transforms": ["middle-out"],
      "provider": {"sort": "throughput"},
  }
  ```
  The `openai` SDK's `create()` accepts `extra_body` natively.
- **Model list:** OpenRouter's `/v1/models` endpoint returns all available models
- **Lines deleted:** ~150 lines of manual httpx + SSE parsing

### 4.3 Cerebras → `OpenAICompatibleProvider`

```
Before: CerebrasProvider(AIProvider) — raw httpx, base_url https://api.cerebras.ai/v1
After:  CerebrasProvider(OpenAICompatibleProvider)
```

- **Base URL:** `https://api.cerebras.ai/v1`
- **Headers:** None special
- **Overrides:** None — vanilla `OpenAICompatibleProvider` behavior
- **Model list:** Cerebras supports `/v1/models`
- **Lines deleted:** ~80 lines of manual httpx + SSE parsing

### 4.4 Ollama → Special Case

```
Before: OllamaProvider(AIProvider) — raw httpx, base_url http://localhost:11434 (native API)
After:  OllamaProvider(OpenAICompatibleProvider) — using Ollama's /v1/ endpoint
```

- **Base URL:** `http://localhost:11434/v1` (Ollama exposes OpenAI-compatible endpoint since v0.1.24)
- **Headers:** API key not required, use `api_key="ollama"` (dummy, required by SDK)
- **Overrides:** `get_available_models()` — use Ollama's native `/api/tags` endpoint (richer metadata) or fall back to `/v1/models`
- **Risk:** Ollama's `/v1/` endpoint may not support `tools` for all models — need graceful fallback
- **Lines deleted:** ~70 lines of manual httpx + NDJSON parsing

---

## 5. Orchestrator Migration Plan

### 5.1 Current Flow (Text-Based Tool Calling)

```
┌─────────────────────────────────────────────────────────────┐
│ handle_user_message() / handle_user_message_streaming()     │
│                                                             │
│  1. Save user message                                       │
│  2. generate_ai_response*() → returns str                   │
│  3. parse_tool_blocks(response_text) → (clean, commands)    │
│  4. for cmd in commands: execute_tool(cmd.name, cmd.args)   │
│  5. format_observation(results) → "<SYSTEM_OBSERVATION>..." │
│  6. generate_ai_response() again → synthesis str            │
│  7. Save synthesis                                          │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 New Flow (Native Tool Calling)

```
┌──────────────────────────────────────────────────────────────────┐
│ handle_user_message() / handle_user_message_streaming()          │
│                                                                  │
│  1. Save user message                                            │
│  2. chat_complete(messages, tools=get_openai_tools())            │
│     → returns ChatCompletion                                     │
│  3. IF response.choices[0].message.tool_calls:                   │
│     a. Save assistant message (with tool_calls metadata)         │
│     b. for tc in tool_calls:                                     │
│          result = execute_tool(tc.function.name,                 │
│                                json.loads(tc.function.arguments))│
│          tool_messages.append({                                  │
│              "role": "tool",                                     │
│              "tool_call_id": tc.id,                              │
│              "content": json.dumps(result),                      │
│          })                                                      │
│     c. chat_complete(messages + [assistant_msg] + tool_messages) │
│        → synthesis ChatCompletion                                │
│     d. Save synthesis content                                    │
│  4. ELSE: save content as normal assistant message                │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Key Differences

| Aspect | Old | New |
|---|---|---|
| Tool detection | Regex parse `<tool>` blocks from text | Check `message.tool_calls` attribute |
| Tool arguments | Single string (`arguments: str`) | Structured JSON (`{"command": "ls -la"}`) |
| Tool results feedback | `<SYSTEM_OBSERVATION>` text block | `role: "tool"` messages with `tool_call_id` |
| Synthesis trigger | Second `generate_ai_response()` call | Second `chat_complete()` call with tool results |
| Fallback | N/A (only path) | Keep `parse_tool_blocks()` for models without function calling support |

### 5.4 `llm_client.py` Changes

The `generate_ai_response*()` functions must be updated to:

1. **Accept `tools` parameter:**
   ```python
   async def generate_ai_response(
       messages: list[dict],
       session_id: int,
       provider_name: str | None = None,
       model: str | None = None,
       tools: list[dict] | None = None,    # NEW
   ) -> ChatCompletion:                      # CHANGED return type
   ```

2. **Return `ChatCompletion` instead of `str`** — let the orchestrator inspect tool calls
3. **Call `provider.chat_complete()` instead of `provider.send_message*()`**
4. **Streaming variant returns `AsyncGenerator[ChatCompletionChunk, None]`**

### 5.5 Direct `provider.send_message()` Call Sites

These 7 call sites bypass `llm_client.py` and must also be migrated:

| File | Line | Current Call | Migration |
|---|---|---|---|
| `memory/memory_review.py` | 36 | `provider.send_message(messages, model)` | `(await provider.chat_complete(messages, model)).choices[0].message.content` |
| `memory/pcl.py` | 79 | `provider.send_message(messages, model)` | Same pattern |
| `memory/pcl.py` | 112 | `provider.send_message(messages, model)` | Same pattern |
| `tools/ask_rei.py` | 80 | `provider.send_message(messages, model)` | Same pattern |
| `tools/db_query.py` | 95 | `provider.send_message(messages, model)` | Same pattern |
| `tools/db_query.py` | 122 | `provider.send_message(messages, model)` | Same pattern |
| `profile_analysis.py` | 22 | `provider.send_message(messages, model)` | Same pattern |

**Strategy:** These are all simple text-generation calls (no tools needed). During transition, the deprecated `send_message()` shim handles them. In a cleanup pass, migrate to `chat_complete()` with explicit content extraction.

### 5.6 `chutes_chat()` Migration

`chutes_chat()` in `llm_client.py` is called 4 times from `memory/memory.py`. It's a convenience function that hardcodes the Chutes provider.

**Migration:** Replace with a generic helper:
```python
async def simple_chat(
    messages: list[dict],
    model: str = "deepseek-ai/DeepSeek-V3-0324",
    provider_name: str = "chutes",
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    provider = get_ai_manager().get_provider(provider_name)
    resp = await provider.chat_complete(
        messages, model, temperature=temperature, max_tokens=max_tokens
    )
    return resp.choices[0].message.content or ""
```

---

## 6. Tool Schema Migration Plan

### 6.1 Current State

Two parallel schema systems exist:

| System | Format | Status |
|---|---|---|
| `TOOL_DEFINITION` (per-tool module) | `{"name", "description", "usage", "examples"}` | Active — used by registry + prompts |
| `TOOL_SCHEMAS` (schemas.py) | OpenAI function calling JSON schema | **Ready but orphaned** |

### 6.2 Migration Steps

#### Step 1: Registry Uses `schemas.py`

Modify `get_tool_definitions()` in `registry.py` to return `schemas.py` schemas instead of legacy `TOOL_DEFINITION` dicts. The legacy `TOOL_DEFINITION` dicts remain in tool modules for backward-compatible `usage`/`examples` metadata (used by help commands).

#### Step 2: `execute_tool()` Accepts Structured Args

Current signature:
```python
async def execute_tool(name: str, arguments: str, session_id: int, ...) -> dict
```

New signature:
```python
async def execute_tool(
    name: str,
    arguments: str | dict,   # Accept both for transition
    session_id: int,
    db: Database | None = None,
    profile_id: int = 1,
    tool_call_id: str | None = None,   # For response correlation
) -> dict
```

When `arguments` is a `dict`, the tool module's `execute()` receives it directly.
When `arguments` is a `str` (legacy path), behavior is unchanged.

#### Step 3: Tool `execute()` Functions Accept `dict`

Each tool's `execute()` function is updated:
```python
# Before:
async def execute(arguments: str, ...) -> dict:
    command = arguments.strip()

# After:
async def execute(arguments: str | dict, ...) -> dict:
    if isinstance(arguments, dict):
        command = arguments["command"]
    else:
        command = arguments.strip()  # Legacy fallback
```

#### Step 4: `prompts.py` Stops Injecting `<tool>` Text

`_build_tool_documentation()` is only needed for models without native function calling. When `tools` is passed to the API, the model knows the tool schemas without prompt injection.

**Approach:** Make `_build_tool_documentation()` conditional:
```python
def _build_tool_documentation(native_tools: bool = False) -> str:
    if native_tools:
        return ""  # API handles tool documentation
    # ... existing text-based documentation
```

### 6.3 Fallback Strategy

Not all models support function calling. The system must support both paths:

```
if model_supports_function_calling(provider, model):
    → pass tools= to chat_complete()
    → inspect response.tool_calls
    → feed back as role="tool" messages
else:
    → inject tool docs in system prompt (existing behavior)
    → parse_tool_blocks() from response text
    → feed back as <SYSTEM_OBSERVATION> text
```

**Model capability detection:** Check if the provider/model supports tools by attempting a call with tools and falling back on `400 Bad Request` or similar errors. Alternatively, maintain a capability map per provider.

---

## 7. Stream Manager Changes

### 7.1 `tool_call_delta` Accumulation During Streaming

When streaming with `tools`, the OpenAI API sends tool calls as deltas across multiple chunks:

```
chunk 1: choices[0].delta.tool_calls[0] = {index: 0, id: "call_abc", function: {name: "bash", arguments: ""}}
chunk 2: choices[0].delta.tool_calls[0] = {index: 0, function: {arguments: '{"com'}}
chunk 3: choices[0].delta.tool_calls[0] = {index: 0, function: {arguments: 'mand"'}}
chunk 4: choices[0].delta.tool_calls[0] = {index: 0, function: {arguments: ': "ls'}}
chunk 5: choices[0].delta.tool_calls[0] = {index: 0, function: {arguments: ' -la"}'}}
chunk 6: choices[0].finish_reason = "tool_calls"
```

### 7.2 Accumulation Logic (In Orchestrator, NOT StreamManager)

> [!IMPORTANT]
> Tool call accumulation should live in the **orchestrator's streaming loop**, not in `StreamManager`.
> `StreamManager` is a generic buffer — it should not know about tool call semantics.

```python
# In handle_user_message_streaming():

tool_call_acc: dict[int, dict] = {}  # index → accumulated tool call
content_parts: list[str] = []

async for chunk in provider.chat_stream(messages, tools=tool_schemas):
    delta = chunk.choices[0].delta

    # Accumulate content (stream to client)
    if delta.content:
        content_parts.append(delta.content)
        yield delta.content  # SSE to frontend

    # Accumulate tool call deltas (buffer silently)
    if delta.tool_calls:
        for tc_delta in delta.tool_calls:
            idx = tc_delta.index
            if idx not in tool_call_acc:
                tool_call_acc[idx] = {
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                }
            if tc_delta.id:
                tool_call_acc[idx]["id"] = tc_delta.id
            if tc_delta.function:
                if tc_delta.function.name:
                    tool_call_acc[idx]["function"]["name"] = tc_delta.function.name
                if tc_delta.function.arguments:
                    tool_call_acc[idx]["function"]["arguments"] += tc_delta.function.arguments

    # Check finish reason
    if chunk.choices[0].finish_reason == "tool_calls":
        # All tool calls are fully accumulated — execute them
        break

# After streaming completes:
if tool_call_acc:
    tool_calls = list(tool_call_acc.values())
    # Execute each tool call...
```

### 7.3 `StreamChunk` Extension (Minimal)

`StreamChunk` needs a new chunk type to signal tool execution progress to the frontend:

```python
@dataclass
class StreamChunk:
    content: str
    chunk_type: str = "content"  # "content", "error", "done", "tool_status"
    timestamp: float = field(default_factory=time.time)
    metadata: dict | None = None  # Optional: {"tool_name": "bash", "status": "executing"}
```

The frontend can use `tool_status` chunks to show "Executing bash…" indicators.

---

## 8. Step-by-Step Execution Order

### Phase A: Provider Foundation (No Orchestrator Changes)

> [!NOTE]
> All deprecated `send_message*` shims remain functional during this phase.
> Existing orchestrator code continues to work unchanged.

| Step | Action | Files | Risk |
|---|---|---|---|
| **A.1** | Add `openai>=1.30.0` to `requirements.txt` | `requirements.txt` | None |
| **A.2** | Create `OpenAICompatibleProvider` in `base.py` | `app/providers/base.py` | Low — additive only |
| **A.3** | Add `chat_complete()` and `chat_stream()` as abstract methods to `AIProvider` | `app/providers/base.py` | Low — shims provide defaults |
| **A.4** | Move `send_message*()` from abstract to deprecated shims (call `chat_complete`/`chat_stream` internally) | `app/providers/base.py` | **Medium** — all providers must implement new interface |
| **A.5** | Migrate `ChutesProvider` → `OpenAICompatibleProvider` | `app/providers/chutes.py` | Medium |
| **A.6** | Migrate `CerebrasProvider` → `OpenAICompatibleProvider` | `app/providers/cerebras.py` | Low |
| **A.7** | Migrate `OpenRouterProvider` → `OpenAICompatibleProvider` | `app/providers/openrouter.py` | Medium (custom headers/body) |
| **A.8** | Migrate `OllamaProvider` → `OpenAICompatibleProvider` | `app/providers/ollama.py` | Medium (API endpoint change) |
| **A.9** | Update `__init__.py` exports | `app/providers/__init__.py` | None |
| **A.10** | Verify: all existing tests pass, `send_message*` shims work | `tests/` | — |

### Phase B: Orchestrator Migration

| Step | Action | Files | Risk |
|---|---|---|---|
| **B.1** | Update `generate_ai_response()` → accept `tools`, return `ChatCompletion` | `app/llm_client.py` | **High** — changes return type |
| **B.2** | Update `generate_ai_response_streaming()` → accept `tools`, yield `ChatCompletionChunk` | `app/llm_client.py` | **High** — changes yield type |
| **B.3** | Update `handle_user_message()` to use native tool calls | `app/orchestrator.py` | **High** — core logic change |
| **B.4** | Update `handle_user_message_streaming()` with `tool_call_delta` accumulation | `app/orchestrator.py` | **High** — streaming + tool calls |
| **B.5** | Update `execute_tool()` to accept `str | dict` arguments | `app/tools/registry.py` | Low |
| **B.6** | Update each tool's `execute()` to accept `str | dict` | `app/tools/*.py` | Low per file |
| **B.7** | Replace `chutes_chat()` with `simple_chat()` | `app/llm_client.py` | Low |
| **B.8** | Migrate direct `provider.send_message()` callers | `memory/`, `tools/`, `profile_analysis.py` | Low (7 sites) |

### Phase C: Prompt & Schema Cleanup

| Step | Action | Files | Risk |
|---|---|---|---|
| **C.1** | Make `_build_tool_documentation()` conditional on native tool support | `app/prompts.py` | Low |
| **C.2** | Wire `get_openai_tools()` from `schemas.py` into orchestrator | `app/orchestrator.py` | Low |
| **C.3** | Keep `parse_tool_blocks()` as fallback for non-function-calling models | `app/commands.py` | None (no change) |
| **C.4** | Update message persistence to handle `tool_calls` metadata | `app/db/queries.py`, `app/db/facade.py` | Medium |

---

## 9. Files Modified per Step

| File | Steps | Total Changes |
|---|---|---|
| `requirements.txt` | A.1 | Add `openai>=1.30.0` |
| `app/providers/base.py` | A.2, A.3, A.4 | New `OpenAICompatibleProvider`, refactored `AIProvider` |
| `app/providers/chutes.py` | A.5 | Rewrite: ~130 lines → ~30 lines |
| `app/providers/cerebras.py` | A.6 | Rewrite: ~80 lines → ~20 lines |
| `app/providers/openrouter.py` | A.7 | Rewrite: ~150 lines → ~40 lines |
| `app/providers/ollama.py` | A.8 | Rewrite: ~70 lines → ~30 lines |
| `app/providers/__init__.py` | A.9 | Add `OpenAICompatibleProvider` export |
| `app/llm_client.py` | B.1, B.2, B.7 | Major refactor — new return types, new helper |
| `app/orchestrator.py` | B.3, B.4, C.2 | Major refactor — native tool call flow |
| `app/tools/registry.py` | B.5 | `execute_tool()` accepts `str | dict` |
| `app/tools/*.py` (10 files) | B.6 | Each `execute()` accepts `str | dict` |
| `app/memory/memory.py` | B.7 | Replace `chutes_chat()` calls |
| `app/memory/memory_review.py` | B.8 | Migrate `provider.send_message()` |
| `app/memory/pcl.py` | B.8 | Migrate `provider.send_message()` (2 sites) |
| `app/tools/ask_rei.py` | B.8 | Migrate `provider.send_message()` |
| `app/tools/db_query.py` | B.8 | Migrate `provider.send_message()` (2 sites) |
| `app/profile_analysis.py` | B.8 | Migrate `provider.send_message()` |
| `app/prompts.py` | C.1 | Conditional tool documentation |
| `app/commands.py` | C.3 | No change (retained as fallback) |
| `app/db/queries.py` | C.4 | Add tool_calls column handling |
| `app/db/facade.py` | C.4 | Add tool_calls to message methods |
| `app/stream_manager.py` | B.4 | Add `tool_status` chunk type + metadata field |

---

## 10. Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Chutes API doesn't fully support OpenAI SDK | Medium | High | Test SDK against Chutes first; if incompatible, keep thin httpx wrapper that still implements `chat_complete` interface |
| Ollama `/v1/` endpoint lacks tool support for some models | High | Medium | `model_supports_tools()` check + text-based fallback path |
| OpenRouter `extra_body` handling differs from SDK expectations | Low | Medium | OpenRouter's API explicitly supports `extra_body` in the OpenAI format |
| Return type change (`str` → `ChatCompletion`) breaks callers | High (during B.1) | High | Deprecated shims in Phase A ensure old callers work; Phase B migrates all callers before removing shims |
| Memory pipeline calls fail during transition | Low | Medium | `simple_chat()` helper provides identical behavior to `chutes_chat()` |
| `openai` SDK adds unwanted dependency weight | Low | Low | `openai` is a lightweight package (~2MB); no transitive heavy deps |
| Database schema change for tool_calls metadata | Medium | Medium | Add nullable `tool_calls_json` column; existing rows unaffected |

---

## Appendix: Full Call Site Map

### All `send_message*` Call Sites (Complete)

```
DEFINITIONS (to be replaced):
  app/providers/base.py:47       send_message         [abstract]
  app/providers/base.py:55       send_message_streaming  [abstract]
  app/providers/base.py:66       send_message_raw     [default impl]
  app/providers/chutes.py:66     send_message         [override]
  app/providers/chutes.py:98     send_message_raw     [override]
  app/providers/chutes.py:132    send_message_streaming  [override]
  app/providers/openrouter.py:75 send_message         [override]
  app/providers/openrouter.py:120 send_message_raw    [override]
  app/providers/openrouter.py:164 send_message_streaming [override]
  app/providers/cerebras.py:45   send_message         [override]
  app/providers/cerebras.py:78   send_message_streaming [override]
  app/providers/ollama.py:59     send_message         [override]
  app/providers/ollama.py:86     send_message_streaming [override]

CALL SITES (to be migrated):
  app/llm_client.py:120          provider.send_message_raw(messages, model)
  app/llm_client.py:163          provider.send_message(messages, model)
  app/llm_client.py:216          provider.send_message(messages, model)
  app/llm_client.py:256          provider.send_message(formatted_messages, model)
  app/llm_client.py:290          provider.send_message_streaming(messages, model)
  app/llm_client.py:342          provider.send_message_streaming(formatted_messages, model)
  app/memory/memory_review.py:36 provider.send_message(messages, model)
  app/memory/pcl.py:79           provider.send_message(messages, model)
  app/memory/pcl.py:112          provider.send_message(messages, model)
  app/tools/ask_rei.py:80        provider.send_message(messages, model)
  app/tools/db_query.py:95       provider.send_message(messages, model)
  app/tools/db_query.py:122      provider.send_message(messages, model)
  app/profile_analysis.py:22     provider.send_message(messages, model)
  app/providers/base.py:73       self.send_message(messages, model, **kwargs)  [from send_message_raw default]

TOTAL: 14 definitions + 14 call sites = 28 references to eliminate
```

### Dependency: `openai` package is NOT in `requirements.txt`

Must be added in Step A.1:
```
openai>=1.30.0
```

### Existing Asset: `app/tools/schemas.py`

OpenAI-format tool schemas already exist for all 10 tools. Functions `get_openai_tools()` and `get_tool_schema()` are defined but **called nowhere** (0 references). These become the canonical tool definitions in Phase C.
