# Agentic Loop Architecture Audit

**Date**: 2026-04-26
**Branch**: `refactor/api-routing-decomposition`
**Scope**: Upgrade to autonomous agentic loop with hybrid tooling (Local RPC + Zo MCP)

---

## Executive Summary

Yuzu Companion already has a **partial agentic loop implementation** in `app/orchestrator_agentic.py`. The core Plan-Execute-Observe loop exists, but several critical components need enhancement:

| Component | Status | Gap |
|-----------|--------|-----|
| Plan-Execute-Observe Loop | ✅ Exists | Not wired to web API |
| Hybrid Dispatcher | ✅ Exists | No startup discovery |
| MCP Client | ✅ Exists | No token validation |
| Command Parser | ✅ Exists | Works for both formats |
| Thought Parser | ✅ Exists | Not used in streaming |
| Stream Parser | ✅ Exists | Not wired to orchestrator |
| Agentic Config | ✅ Exists | No UI controls |

---

## Current Architecture

### 1. Core Files

```
app/
├── orchestrator.py              # Single-pass (one tool per turn)
├── orchestrator_agentic.py      # Multi-turn loop (exists but unused)
├── agentic_config.py            # Mode toggle + status
│
├── agents/
│   ├── config.py                # AgentConfig (max_iterations=50, timeout=30min)
│   ├── command_parser.py        # [COMMAND: tool(args)] + /slash
│   ├── thought_parser.py        # <thought>...</thought>
│   └── stream_parser.py         # Buffer-based streaming parser
│
├── dispatch/
│   ├── __init__.py
│   └── hybrid.py                # Routes local → MCP
│
├── mcp/
│   ├── README.md
│   ├── __init__.py
│   └── client.py                # HTTP JSON-RPC to Zo MCP
│
├── tools/
│   ├── __init__.py
│   ├── registry.py              # Local tool dispatch
│   ├── schemas.py               # ToolDefinition dataclass
│   ├── image_generate.py        # /imagine
│   ├── http_request.py          # /request
│   ├── memory_store.py          # /memory_store
│   ├── memory_search.py         # /memory_search
│   ├── file_read.py             # /file_read
│   ├── list_dir.py              # /list_dir
│   └── multimodal.py            # Vision/image helpers
│
└── prompts.py                   # System prompt assembly
```

### 2. Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CURRENT FLOW (orchestrator.py)                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   User Message ──▶ LLM Response ──▶ Command? ──▶ No ──▶ Return         │
│                          │               │                               │
│                          │               ▼                               │
│                          │           Execute Tool                         │
│                          │               │                               │
│                          │               ▼                               │
│                          │         Synthesis Pass                         │
│                          │               │                               │
│                          ▼               ▼                               │
│                      Persist ◀─────────▶ Return                          │
│                                                                          │
│   LIMITATION: ONE tool execution per turn MAX                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENTIC FLOW (orchestrator_agentic.py)               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐              │
│   │  PLAN  │───▶│ EXECUTE │───▶│ OBSERVE  │───▶│ Loop?   │──┐           │
│   └────────┘    └─────────┘    └──────────┘    └─────────┘  │           │
│        ▲                                           │ No     │           │
│        │                                           ▼        │           │
│        │                                     ┌─────────┐   │           │
│        │                                     │  DONE   │◀──┘           │
│        └─────────────────────────────────────┴─────────┘               │
│                                                                          │
│   STATUS: Implemented but NOT wired to web API                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3. Hybrid Dispatcher Logic

```python
# app/dispatch/hybrid.py

class HybridDispatcher:
    async def execute(tool_name, arguments, session_id):
        if is_local_tool(tool_name):
            return await _execute_local(tool_name, arguments, session_id)
        elif is_mcp_tool(tool_name):
            return await _execute_mcp(tool_name, arguments)
        else:
            return {"ok": False, "error": f"Unknown tool: {tool_name}"}
```

**Current Local Tools:**
- `imagine` / `image_generate`
- `request` / `http_request`
- `memory_store`
- `memory_search`
- `file_read`
- `list_dir`

**MCP Tools (56+):**
- `web_search`, `web_research`, `maps_search`
- `read_file`, `edit_file`, `run_bash_command`
- `send_email`, `x_search`, `image_search`
- ... and 40+ more via Zo MCP

---

## Gap Analysis

### Critical Gaps

| ID | Gap | Impact | Priority |
|----|-----|--------|----------|
| G1 | Agentic orchestrator not wired to web API | Users can't use multi-turn tools | P0 |
| G2 | No MCP tool discovery at startup | LLM doesn't know MCP tools exist | P0 |
| G3 | StreamParser not used in streaming path | Commands split across chunks fail | P1 |
| G4 | No agentic mode UI toggle | Users can't enable MCP tools | P1 |
| G5 | No ZO_ACCESS_TOKEN validation | Silent failure if token missing/invalid | P1 |

### Enhancement Opportunities

| ID | Enhancement | Benefit |
|----|-------------|---------|
| E1 | Parallel tool execution | Faster multi-tool workflows |
| E2 | Tool result summarization | Handle large outputs |
| E3 | Retry logic for failed tools | Resilience |
| E4 | Tool permission gating | Safety for sensitive tools |
| E5 | Agentic status UI | Show iteration count, elapsed time |

---

## Integration Points

### Web API (app/api/routes.py)

```python
# Current: Single-pass streaming
@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    for chunk in handle_user_message_streaming(request.message):
        yield chunk

# Needed: Agentic streaming with SSE events
@router.post("/chat/agentic/stream")
async def agentic_stream(request: ChatRequest):
    async for event in stream_agentic_loop(request.message, session_id):
        yield event  # event: thought, event: command, event: tool_result, event: text
```

### Frontend (static/js/)

Current SSE handling:
```javascript
eventSource.onmessage = (event) => {
    appendChunk(event.data);
};
```

Needed for agentic:
```javascript
eventSource.addEventListener('thought', (e) => showThinking(e.data));
eventSource.addEventListener('command', (e) => showToolExecution(e.data));
eventSource.addEventListener('tool_result', (e) => showToolResult(e.data));
eventSource.addEventListener('text', (e) => appendChunk(e.data));
eventSource.addEventListener('done', (e) => showAgenticStats(e.data));
```

---

## Configuration

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ZO_ACCESS_TOKEN` | Yes (for MCP) | Bearer token for Zo MCP API |
| `AGENTIC_MAX_ITERATIONS` | No | Override default 50 |
| `AGENTIC_TIMEOUT_SECONDS` | No | Override default 1800 |

### Profile Settings (providers_config)

```json
{
    "agentic_mode": true,
    "think_mode": true
}
```

---

## Breaking Changes Assessment

| Change | Impact | Migration |
|--------|--------|-----------|
| New SSE event types | Frontend must handle new events | Backward compatible (unknown events ignored) |
| Async-only agentic path | Blocking code paths need async wrapper | Legacy path preserved |
| MCP token required | MCP tools unavailable without token | Graceful degradation to local only |

---

## Recommendations

### Phase 1: Wire Existing Agentic Loop (P0)
1. Add `/api/chat/agentic/stream` endpoint
2. Use `stream_agentic_loop()` from `orchestrator_agentic.py`
3. Add frontend SSE handlers for new event types

### Phase 2: Startup Discovery (P0)
1. Initialize `HybridDispatcher` at FastAPI lifespan
2. Cache MCP tools in `get_mcp_client()._tools_cache`
3. Include MCP tools in `build_system_message()`

### Phase 3: Stream Parser Integration (P1)
1. Replace `StreamFilter` with `AgenticStreamParser` in streaming path
2. Handle split-chunk commands correctly

### Phase 4: UI Controls (P1)
1. Add agentic mode toggle in settings
2. Add agentic status bar (iterations, elapsed)
3. Add thinking/thought display component

---

## Test Coverage

Existing tests:
- `tests/test_agents_phase1.py` - Parser tests

Needed tests:
- `tests/test_agentic_loop.py` - Full loop integration
- `tests/test_hybrid_dispatcher.py` - Local/MCP routing
- `tests/test_mcp_client.py` - JSON-RPC communication
- `tests/test_stream_parser.py` - Chunk boundary handling

---

## References

- MCP Spec: https://spec.modelcontextprotocol.io/
- Zo MCP Endpoint: `https://api.zo.computer/mcp`
- JSON-RPC 2.0: https://www.jsonrpc.org/specification
