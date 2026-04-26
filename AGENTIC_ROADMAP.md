# Agentic Loop Implementation Roadmap

**Branch**: `feature/agentic-loop-v2`
**Base**: `refactor/api-routing-decomposition`
**Estimated Phases**: 4
**Dependencies**: Pure Python + httpx (Termux aarch64 compatible)

---

## Pre-Requisites

- [ ] Merge `refactor/api-routing-decomposition` to main
- [ ] Verify `ZO_ACCESS_TOKEN` available in environment
- [ ] Run `tests/test_agents_phase1.py` to confirm parser functionality

---

## Phase 1: Wire Existing Agentic Loop (P0)

**Goal**: Make the existing `orchestrator_agentic.py` accessible via web API

**Status**: ✅ DONE - API endpoint `/api/agentic/chat` already exists in `app/api/routes.py`

**Files Changed**:
```
app/api/routes.py           # New agentic streaming endpoint
web.py                      # Register agentic router (if needed)
static/js/chat.js           # New SSE event handlers
static/css/renderer.css     # Agentic UI styles (already partially done)
```

### Tasks

#### 1.1 Add Agentic Streaming Endpoint

```python
# app/api/routes.py

from app.orchestrator_agentic import stream_agentic_loop

@router.post("/chat/agentic/stream")
async def agentic_stream(request: ChatRequest):
    """Agentic Plan-Execute-Observe loop with SSE events."""
    session = get_or_create_session()
    
    async def generate():
        async for sse_event in stream_agentic_loop(
            request.message, 
            session["id"], 
            interface="web"
        ):
            yield sse_event
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

#### 1.2 Frontend SSE Handlers

```javascript
// static/js/chat.js

function handleAgenticStream(message) {
    const eventSource = new EventSource(`/api/chat/agentic/stream?message=${encodeURIComponent(message)}`);
    
    eventSource.addEventListener('thought', (e) => {
        const data = JSON.parse(e.data);
        showThinkingBlock(data.content, data.planning, data.tools);
    });
    
    eventSource.addEventListener('command', (e) => {
        const data = JSON.parse(e.data);
        showToolExecution(data.tool, data.args, data.iteration);
    });
    
    eventSource.addEventListener('tool_result', (e) => {
        const data = JSON.parse(e.data);
        showToolResult(data.ok, data.output);
    });
    
    eventSource.addEventListener('text', (e) => {
        appendChunk(JSON.parse(e.data).chunk);
    });
    
    eventSource.addEventListener('done', (e) => {
        const data = JSON.parse(e.data);
        showAgenticStats(data.iterations, data.elapsed, data.tools_used);
        eventSource.close();
    });
    
    eventSource.addEventListener('timeout', (e) => {
        showTimeoutWarning(JSON.parse(e.data).elapsed);
    });
}
```

#### 1.3 UI Components (CSS exists, verify JS)

- `BrainBox` - Thought display (collapsible)
- `ToolExecution` - Tool in-progress indicator
- `ToolResult` - Tool output display
- `AgenticStatusBar` - Fixed bottom bar with stats

**Verification**:
```bash
curl -X POST http://localhost:8000/api/chat/agentic/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for latest Rust news and summarize"}' \
  --no-buffer
```

---

## Phase 2: Startup Discovery (P0)

**Goal**: Initialize MCP tools at server startup, not on first request

**Status**: ✅ DONE - Lifespan handler in `web.py` already initializes HybridDispatcher

**Files Changed**:
```
web.py                      # Lifespan handler
app/dispatch/hybrid.py      # Eager init method
app/prompts.py              # Include MCP tools in system prompt
```

### Tasks

#### 2.1 Lifespan Initialization

```python
# web.py

from contextlib import asynccontextmanager
from app.dispatch.hybrid import get_dispatcher

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("[lifespan] Initializing hybrid dispatcher...")
    dispatcher = get_dispatcher()
    await dispatcher.initialize()
    
    tool_count = len(dispatcher.get_all_tools())
    mcp_count = len(dispatcher.get_mcp_tools())
    log.info(f"[lifespan] Ready | total={tool_count} | mcp={mcp_count}")
    
    yield
    
    # Shutdown
    log.info("[lifespan] Shutting down")
    # Close MCP client if needed
    from app.mcp.client import get_mcp_client
    client = get_mcp_client()
    if client._client:
        await client.close()

app = FastAPI(lifespan=lifespan)
```

#### 2.2 Enhanced Tool Description in System Prompt

```python
# app/prompts.py

def get_mcp_tools_description(profile: dict | None = None) -> str:
    """Generate full MCP tools list for system prompt."""
    if not is_agentic_mode_enabled(profile):
        return ""
    
    from app.dispatch.hybrid import get_dispatcher
    dispatcher = get_dispatcher()
    
    if not dispatcher._initialized:
        return ""  # Will be populated after startup
    
    tools = dispatcher.get_mcp_tools()
    lines = []
    
    for tool in tools[:30]:  # Show top 30
        desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
        lines.append(f"- {tool.name} — {desc}")
    
    if len(tools) > 30:
        lines.append(f"... and {len(tools) - 30} more tools")
    
    return "\n".join(lines)
```

#### 2.3 Tool Schema Injection for LLM

```python
# app/prompts.py

def build_system_message(profile, session_id, interface, user_message):
    # ... existing code ...
    
    # Add tool schemas for agentic mode
    if is_agentic_mode_enabled(profile):
        dispatcher = get_dispatcher()
        if dispatcher._initialized:
            tool_schemas = [t.to_llm_schema() for t in dispatcher.get_all_tools()]
            # Inject into system prompt or use tools[] array in API call
```

**Verification**:
```bash
# Check startup logs
python web.py 2>&1 | grep -E "(lifespan|hybrid|mcp)"

# Should see:
# [lifespan] Initializing hybrid dispatcher...
# Loaded 6 local tools
# Discovered 56 Zo MCP tools
# [lifespan] Ready | total=62 | mcp=56
```

---

## Phase 3: Stream Parser Integration (P1)

**Goal**: Handle commands split across streaming chunks correctly

**Status**: ✅ DONE - AgenticStreamParser integrated into `run_streaming()` in `app/orchestrator_agentic.py`

**Files Changed**:
```
app/orchestrator.py          # Replace StreamFilter with AgenticStreamParser
app/orchestrator_agentic.py  # Use AgenticStreamParser in streaming path
```

### Tasks

#### 3.1 Replace StreamFilter in Single-Pass Path

```python
# app/orchestrator.py

from app.agents.stream_parser import AgenticStreamParser

def handle_user_message_streaming(user_message, interface="terminal"):
    # ... existing setup ...
    
    parser = AgenticStreamParser()
    visible_chunks = []
    
    for chunk in generate_ai_response_streaming(...):
        for safe_chunk, meta in parser.feed(chunk):
            visible_chunks.append(safe_chunk)
            yield safe_chunk
            
            if meta.command:
                # Handle command immediately (already parsed correctly)
                pass
    
    # Final flush
    for safe_chunk, meta in parser.flush():
        visible_chunks.append(safe_chunk)
        yield safe_chunk
    
    # Access parsed state
    commands = parser.commands
    thoughts = parser.thoughts
```

#### 3.2 Agentic Streaming with Parser

```python
# app/orchestrator_agentic.py

async def run_streaming(self, user_message, session_id, interface="web"):
    parser = AgenticStreamParser()
    current_text = ""
    
    # Stream initial LLM response
    async for chunk in self._stream_llm(user_message, session_id, interface, 0):
        current_text += chunk
        
        for safe_chunk, meta in parser.feed(chunk):
            if meta.thought:
                yield {"type": "thought", "data": meta.thought.to_dict()}
            elif meta.command:
                yield {"type": "command", "data": meta.command.to_dict()}
            else:
                yield {"type": "text", "data": {"chunk": safe_chunk}}
    
    # Final flush
    for safe_chunk, meta in parser.flush():
        # ... handle remaining ...
```

**Verification**:
- Test with LLM that outputs commands split across chunks
- Verify parser correctly buffers incomplete patterns

---

## Phase 4: UI Controls & Polish (P1)

**Goal**: User-facing controls for agentic mode

**Files Changed**:
```
templates/settings.html       # Agentic mode toggle
static/js/config.js          # Toggle handler
static/css/chat.css          # Status bar styles
```

### Tasks

#### 4.1 Settings Toggle

```html
<!-- templates/settings.html -->

<div class="setting-group">
    <label for="agentic-mode">
        <strong>Agentic Mode</strong>
        <small>Enable multi-turn tool execution with Zo MCP tools</small>
    </label>
    <label class="switch">
        <input type="checkbox" id="agentic-mode" 
               {% if agentic_enabled %}checked{% endif %}>
        <span class="slider"></span>
    </label>
    <p class="hint">
        Requires ZO_ACCESS_TOKEN. 
        Current status: <span id="mcp-status">{{ mcp_status }}</span>
    </p>
</div>
```

#### 4.2 Status Display

```javascript
// static/js/config.js

async function updateAgenticStatus() {
    const resp = await fetch('/api/agentic/status');
    const status = await resp.json();
    
    document.getElementById('agentic-status').innerHTML = `
        <div class="agentic-stats">
            <span>Local tools: ${status.local_tools_count}</span>
            <span>MCP tools: ${status.mcp_tools_count}</span>
            <span>Total: ${status.total_tools_count}</span>
        </div>
    `;
}
```

#### 4.3 Agentic Status Bar (Already in CSS)

```css
/* static/css/renderer.css - verify these exist */

.agentic-status-bar {
    position: fixed;
    bottom: 70px;
    left: 50%;
    transform: translateX(-50%);
    /* ... */
}

.agentic-stop-btn {
    /* Stop button for user to halt long-running loops */
}
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_agentic_loop.py

import pytest
from app.orchestrator_agentic import AgenticOrchestrator

@pytest.mark.asyncio
async def test_single_tool_execution():
    orch = AgenticOrchestrator()
    result = await orch.run("Search for Rust news", session_id=1)
    assert result.iterations >= 1
    assert len(result.tool_calls) >= 1

@pytest.mark.asyncio
async def test_max_iterations_limit():
    config = AgentConfig(max_iterations=3)
    orch = AgenticOrchestrator(config)
    # Force infinite loop scenario
    # Assert iterations <= 3

@pytest.mark.asyncio
async def test_timeout():
    config = AgentConfig(total_timeout_seconds=5)
    orch = AgenticOrchestrator(config)
    # Long-running tool
    # Assert timeout triggered
```

### Integration Tests

```python
# tests/test_hybrid_dispatcher.py

@pytest.mark.asyncio
async def test_local_tool_priority():
    disp = HybridDispatcher()
    await disp.initialize()
    
    # Local tool should take priority over MCP if name collision
    result = await disp.execute("imagine", {"prompt": "test"})
    assert result["ok"]
    assert "local" in result.get("source", "")

@pytest.mark.asyncio
async def test_mcp_fallback():
    disp = HybridDispatcher()
    await disp.initialize()
    
    # MCP-only tool
    result = await disp.execute("web_search", {"query": "test", "time_range": "anytime"})
    assert result["ok"] or "token" in result.get("error", "").lower()
```

---

## Rollback Plan

If issues arise:

1. **Feature Flag**: Add `ENABLE_AGENTIC_LOOP=false` env var
2. **Fallback Endpoint**: Keep `/api/chat/stream` as single-pass
3. **Frontend Toggle**: Disable agentic mode in settings

---

## Success Metrics

| Metric | Target |
|--------|--------|
| MCP tool discovery time | < 2s at startup |
| First tool execution latency | < 500ms |
| Max iterations enforced | 100% compliance |
| Timeout enforced | 100% compliance |
| Graceful degradation | MCP tools unavailable → local only works |

---

## Dependencies

```txt
# requirements.txt (already satisfied)
httpx>=0.25.0      # MCP client
asyncio            # Standard library
dataclasses        # Standard library
```

**No Rust dependencies** - Pure Python + httpx for Termux aarch64 compatibility.

---

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1 | 1-2 days | None |
| Phase 2 | 1 day | Phase 1 |
| Phase 3 | 1-2 days | Phase 1 |
| Phase 4 | 1 day | Phase 1-3 |

**Total**: 4-6 days
