# Yuzu Companion - Tools Refactor Roadmap

**Version:** 1.0  
**Date:** 2026-03-13  
**Status:** Planning Phase

---

## Executive Summary

This roadmap outlines the complete refactor of Yuzu Companion's tool system to achieve:

1. **Seamless tool execution** - Users never see raw commands
2. **Unified tool interface** - Internal tools and MCP servers share same UX
3. **Real-time feedback** - WebSocket-powered live tool status
4. **Termux compatibility** - Full MCP support on Android

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │  Chat Input │  │  Message    │  │  Tool Card      │   │
│  │             │  │  Bubble     │  │  (loading/      │   │
│  │             │  │             │  │   result)       │   │
│  └─────────────┘  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 TOOL ORCHESTRATION LAYER                 │
│                                                          │
│  ┌──────────────┐    ┌─────────────┐    ┌───────────┐  │
│  │ Intent       │───▶│ Tool        │───▶│ Result    │  │
│  │ Detector     │    │ Executor    │    │ Processor │  │
│  │ (LLM decides│    │ (MCP +      │    │ (Format   │  │
│  │  tool need)  │    │  Internal)  │    │  for UI)   │  │
│  └──────────────┘    └─────────────┘    └───────────┘  │
│         │                   │                  │         │
│         ▼                   ▼                  ▼         │
│  ┌─────────────────────────────────────────────────────┐ │
│  │           UNIFIED TOOL INTERFACE                     │ │
│  │  • Internal tools (image_generate, web_search)    │ │
│  │  • MCP tools (filesystem, fetch, sqlite)          │ │
│  │  • All expose same interface to orchestration     │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    DATABASE LAYER                        │
│  • Messages table (user, assistant, tool_results)       │
│  • Tool executions table (audit trail)                 │
│  • MCP servers configuration                           │
│  • Tool results stored as structured JSON               │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 0: Foundation (Audit & Design)

### 0.1 Current State Documentation

| Task | Output | Priority |
|------|--------|----------|
| Document current tool execution flow | Sequence diagram | High |
| Map all tool entry points | Table (file:line for each tool) | High |
| Document current DB schema for tools | ERD snippet | Medium |
| Inventory current UI rendering | Screenshot + code refs | Medium |

### 0.2 Target UI Design System

#### Message Types

| Type | Visual | Use Case |
|------|--------|----------|
| `text` | Plain bubble | Regular chat |
| `tool_pending` | Card with spinner + status text | Tool running |
| `tool_result` | Card with result content | Tool complete |
| `hybrid` | Text bubble + inline result | Image generation |

#### Tool Card Component

```
┌────────────────────────────────┐
│ 🖼️  Image Generation           │  ← Header (icon + name)
├────────────────────────────────┤
│                                │
│  [image preview or spinner]    │  ← Content area
│                                │
├────────────────────────────────┤
│ "here you go~ 🌸"             │  ← LLM commentary
└────────────────────────────────┘
```

#### Card Variants by Tool

| Tool | Icon | Loading State | Result Display |
|------|------|---------------|----------------|
| Image Generate | 🖼️ | "Creating image..." | Image + caption |
| Web Search | 🔍 | "Searching..." | Result list |
| Weather | 🌤️ | "Checking forecast..." | Weather card |
| Filesystem (MCP) | 📝 | "Reading file..." | File content |
| Fetch (MCP) | 🌐 | "Fetching page..." | Page summary |

---

## Phase 1: Database Schema

### 1.1 New Tables

**tool_executions**
```sql
CREATE TABLE tool_executions (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL,
    message_id INTEGER,
    tool_type VARCHAR(20) NOT NULL,  -- 'internal' | 'mcp'
    tool_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,     -- 'pending' | 'running' | 'success' | 'error'
    input_params JSON,
    output_result JSON,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id),
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

CREATE INDEX idx_tool_exec_session ON tool_executions(session_id);
CREATE INDEX idx_tool_exec_status ON tool_executions(status);
```

**mcp_servers**
```sql
CREATE TABLE mcp_servers (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    transport VARCHAR(10) NOT NULL,  -- 'stdio' | 'http'
    command VARCHAR(255),            -- for stdio transport
    args JSON,                       -- command arguments
    url VARCHAR(255),                -- for http transport
    env_vars JSON,
    is_active BOOLEAN DEFAULT TRUE,
    is_connected BOOLEAN DEFAULT FALSE,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 1.2 Modified Tables

**messages**
- Add `tool_execution_id INTEGER` (nullable, FK to tool_executions)
- Add `render_mode VARCHAR(20)` (default: 'text')
- Add `has_tool_result BOOLEAN` (default: FALSE)

---

## Phase 2: Tool Orchestration Engine

### 2.1 Core Components

#### A. IntentDetector

**Responsibility:** Determine if user request needs a tool

**Input:**
- User message text
- Conversation context (last 3 messages)
- Available tools list

**Output:**
```python
class ToolIntent:
    tool_name: str
    params: dict
    confidence: float  # 0.0 - 1.0
    reasoning: str
```

**Implementation:**
- LLM prompt with few-shot examples
- Structured output (JSON)
- Confidence threshold: 0.7

#### B. ToolRouter

**Responsibility:** Route to correct tool implementation

**Supported Tool Types:**
| Type | Example | Execution Method |
|------|---------|------------------|
| Internal | image_generate | Python function call |
| MCP Stdio | filesystem | Subprocess spawn |
| MCP HTTP | remote tool | HTTP POST |

**Interface:**
```python
class ToolRouter:
    def execute(self, tool_intent: ToolIntent) -> ToolResult:
        if tool_intent.tool_type == 'internal':
            return self._execute_internal(tool_intent)
        elif tool_intent.tool_type == 'mcp_stdio':
            return self._execute_mcp_stdio(tool_intent)
        elif tool_intent.tool_type == 'mcp_http':
            return self._execute_mcp_http(tool_intent)
```

#### C. ResultProcessor

**Responsibility:** Transform raw output to UI-ready format

**Input:** Raw tool output (bytes, JSON, string)
**Output:** UI specification object

```python
class ToolCardSpec:
    card_type: str           # 'image', 'text', 'list', 'code', 'error'
    header_icon: str         # emoji
    header_title: str        # tool display name
    content: Any             # rendered content
    llm_commentary: str      # optional LLM text
    raw_result: dict         # for DB storage
```

### 2.2 Execution Flow

```
User: "What's the weather?"
    │
    ▼
┌─────────────────┐
│ 1. Intent       │
│    Detection    │
│    (LLM call)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     No tool detected
│ 2. Tool needed? │─────────────────▶ Direct LLM response
└────────┬────────┘
         │ Yes
         ▼
┌─────────────────┐
│ 3. Create DB    │
│    Execution    │
│    (pending)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     WebSocket: tool_update (running)
│ 4. Execute Tool │
│    (async)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. Update DB    │
│    (success/    │
│    error)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     WebSocket: tool_complete
│ 6. Process      │
│    Result       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 7. Stream to UI │
│    (card +      │
│    commentary)  │
└─────────────────┘
```

---

## Phase 3: UI Component System

### 3.1 Component Hierarchy

```
ChatContainer
├── MessageBubble (existing)
│   ├── TextContent
│   └── Timestamp
│
└── ToolCard (new)
    ├── CardHeader
    │   ├── Icon
    │   └── Title
    ├── CardBody
    │   ├── LoadingState (spinner)
    │   ├── ImageResult
    │   ├── TextResult
    │   ├── ListResult
    │   └── ErrorState
    └── CardFooter (optional)
        └── LLM commentary
```

### 3.2 Rendering Logic

| Tool Status | UI Component | Behavior |
|-------------|--------------|----------|
| `pending` | Skeleton card | Show immediately after intent detection |
| `running` | Card + spinner | Animate, show status text |
| `success` | Card + result | Display formatted result |
| `error` | Error card | Red styling, error message |

---

## Phase 4: MCP Integration

### 4.1 MCP Architecture

```
┌─────────────────────────────────┐
│        MCP Manager              │
├─────────────────────────────────┤
│ • Server lifecycle management   │
│ • Connection pooling            │
│ • Capability discovery          │
│ • Error handling & retry        │
└─────────────┬───────────────────┘
              │
    ┌─────────┴──────────┐
    ▼                    ▼
┌──────────┐      ┌──────────┐
│ Stdio    │      │ HTTP/SSE │
│ Transport│      │ Transport│
│ (spawn)  │      │ (fetch)  │
└──────────┘      └──────────┘
```

### 4.2 Recommended MCP Servers

| Server | Use Case | Termux Compatible |
|--------|----------|-------------------|
| `@modelcontextprotocol/server-filesystem` | Read/write local files | ✅ Yes |
| `mcp-server-fetch` | Fetch any URL | ✅ Yes |
| `@modelcontextprotocol/server-sqlite` | Query SQLite databases | ✅ Yes |
| `@modelcontextprotocol/server-memory` | Persistent key-value storage | ✅ Yes |
| `@modelcontextprotocol/server-github` | Read GitHub repos | ⚠️ Needs token |
| `@modelcontextprotocol/server-brave-search` | Web search | ⚠️ Needs API key |

### 4.3 Termux Configuration Example

```json
{
  "mcp_servers": [
    {
      "name": "notes",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/sdcard/Documents/yuzu-notes"],
      "env": {},
      "auto_start": true
    },
    {
      "name": "fetch",
      "transport": "stdio",
      "command": "uvx",
      "args": ["mcp-server-fetch"],
      "env": {}
    }
  ]
}
```

---

## Phase 5: WebSocket Implementation

### 5.1 Why WebSocket

| Feature | HTTP Polling | WebSocket |
|---------|-------------|-----------|
| Latency | 500ms-1s | <100ms |
| Tool progress | Delayed updates | Real-time streaming |
| Server push | Not possible | Native support |
| Connection reuse | Each request new | Persistent |

### 5.2 Protocol Specification

#### Client → Server Messages

```typescript
interface UserMessage {
  type: 'message';
  id: string;           // client-generated UUID
  content: string;
  session_id: string;
  timestamp: number;
}

interface TypingStatus {
  type: 'typing';
  session_id: string;
  is_typing: boolean;
}
```

#### Server → Client Messages

```typescript
interface ToolUpdate {
  type: 'tool_update';
  execution_id: string;
  tool_name: string;
  status: 'pending' | 'running' | 'success' | 'error';
  progress?: number;      // 0-100, optional
  status_text?: string;   // "Fetching page..."
}

interface AssistantChunk {
  type: 'stream_chunk';
  message_id: string;
  content: string;
  is_tool_commentary?: boolean;
}

interface ToolComplete {
  type: 'tool_complete';
  execution_id: string;
  card_spec: ToolCardSpec;
  llm_prompt?: string;    // Context for follow-up LLM call
}

interface ErrorMessage {
  type: 'error';
  code: string;
  message: string;
}
```

### 5.3 Connection Lifecycle

```
┌─────────────┐
│   Page      │
│   Loads     │
└──────┬──────┘
       │
       ▼
┌───────────────┐
│ WS Connect    │
│ /ws?sid=xxx   │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Server        │
│ Validates     │
│ Session       │
└───────┬───────┘
        │
    ┌───┴───┐
    ▼       ▼
┌──────┐ ┌──────┐
│Valid │ │Invalid│
└───┬──┘ └───┬──┘
    │        │
    ▼        ▼
┌──────┐  ┌──────┐
│Open  │  │Close │
│      │  │401   │
└──┬───┘  └──────┘
   │
   ▼
┌──────────────────┐
│ Bidirectional   │
│ Message Flow    │
└──────────────────┘
```

---

## Phase 6: Implementation Schedule

### Week 1: Core Refactor

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Create orchestration package structure | `orchestration/` directory |
| 2 | Implement IntentDetector | Unit tests passing |
| 3 | Implement ToolRouter | Internal tools migrated |
| 4 | Implement ResultProcessor | Output formatting working |
| 5 | Create DB migrations | Schema updated |
| 6 | Update message rendering | Cards display correctly |
| 7 | Week 1 integration test | All internal tools working |

### Week 2: MCP Foundation

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | MCP client library | Can connect to stdio server |
| 2 | MCP tool discovery | Lists available tools |
| 3 | MCP stdio execution | Filesystem server working |
| 4 | MCP config UI | Add/edit servers in config page |
| 5 | MCP error handling | Graceful failures |
| 6 | Week 2 integration test | MCP + internal tools coexist |
| 7 | Buffer day | Bug fixes |

### Week 3: WebSocket

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | WebSocket server setup | Flask-SocketIO integration |
| 2 | Client connection | JS WebSocket client |
| 3 | Message streaming | AI responses stream in real-time |
| 4 | Tool progress updates | Live status during execution |
| 5 | Reconnection logic | Auto-reconnect on disconnect |
| 6 | Week 3 integration test | Full flow with WebSocket |
| 7 | Buffer day | Bug fixes |

### Week 4: Integration & Polish

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | All internal tools migrated | Image, weather, search |
| 2 | MCP servers fully integrated | Filesystem, fetch, sqlite |
| 3 | UI polish | Animations, transitions |
| 4 | Mobile testing | All features work on Android/Termux |
| 5 | Documentation | Architecture docs updated |
| 6 | End-to-end testing | Full test suite passing |
| 7 | Release preparation | Merge to main |

---

## Phase 7: Testing Strategy

### 7.1 Test Categories

| Category | Coverage | Tools |
|------------|----------|-------|
| Unit | IntentDetector, ToolRouter, ResultProcessor | pytest |
| Integration | DB operations, API endpoints | pytest + testclient |
| E2E | Full user flows | Manual + automated |
| MCP | Server communication | mcp test client |
| Mobile | Touch, viewport, performance | Chrome DevTools |

### 7.2 Critical Test Scenarios

| Scenario | Steps | Expected |
|----------|-------|----------|
| Image generation | Request image → detect intent → execute → render | Shows loading, then image + text |
| MCP filesystem | "Read my notes" → MCP call → file content | Reads file, displays content |
| Concurrent tools | Request multiple things rapidly | Queues properly, no race conditions |
| Network failure | Tool execution during disconnect | Shows error card, can retry |
| Reconnection | WebSocket drops then reconnects | Seamless resume, no data loss |

---

## Decision Log

This section records architectural decisions made during implementation.

### Decision 1: Implementation Order

**Options:**
- A. MCP first, then UI refactor
- B. UI refactor first, then MCP
- C. WebSocket first, then tools

**Decision:** **B** - UI refactor first

**Rationale:**
- Existing tools need the new UI immediately
- MCP can use the same UI components once built
- Lower risk - improves existing features first

**Status:** Pending confirmation

---

### Decision 2: WebSocket Scope

**Options:**
- A. WebSocket for everything (replace HTTP)
- B. WebSocket only for tool updates, keep HTTP for chat
- C. HTTP for now, WebSocket in Phase 2

**Decision:** **B** - Hybrid approach

**Rationale:**
- Tool updates benefit most from real-time
- Chat works fine over HTTP with SSE fallback
- Lower complexity than full WebSocket migration

**Status:** Pending confirmation

---

### Decision 3: Tool Visibility

**Options:**
- A. Always show tool cards (transparent)
- B. Hide tool details, only show results (seamless)
- C. Configurable per user preference

**Decision:** **B** - Seamless/hidden

**Rationale:**
- Matches user request: "flow must seamless"
- Tool execution is implementation detail
- Error states can still show diagnostics

**Status:** Pending confirmation

---

### Decision 4: MCP Auto-Setup

**Options:**
- A. Auto-install common MCP servers (filesystem, fetch)
- B. User manually configures all
- C. Wizard guides first-time setup

**Decision:** **C** - Setup wizard

**Rationale:**
- Auto-install too magic/error-prone
- Manual too hard for users
- Wizard balances ease and control

**Status:** Pending confirmation

---

### Decision 5: Termux Priority

**Question:** Is Termux/Android a first-class target?

**Decision:** **Yes**

**Implications:**
- All MCP servers must work in Termux
- WebSocket must handle mobile network changes
- UI must work with mobile keyboard
- Documentation includes Termux sections

**Status:** Confirmed

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| MCP servers crash in Termux | Medium | High | Auto-restart, fallback to internal tools |
| WebSocket unstable on mobile | Medium | Medium | HTTP fallback, reconnection logic |
| LLM intent detection unreliable | Medium | High | Confidence threshold, user confirmation |
| Database migration issues | Low | High | Backup before migrate, rollback plan |
| Scope creep (too many tools) | High | Medium | Strict phase gates, MVP first |

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Tool execution perceived delay | 2-5s | <1s | User timing test |
| Tool UI clarity | 60% | 90% | User survey |
| MCP server stability | N/A | 99% | Uptime tracking |
| Code complexity (cyclomatic) | High | Medium | Static analysis |
| Mobile compatibility | Partial | Full | Test suite |

---

## Next Steps

1. **Review this roadmap** - Confirm decisions above
2. **Create Phase 0 tickets** - Audit tasks in issue tracker
3. **Set up feature branch** - `feature/tools-refactor`
4. **Begin Phase 0** - Current state documentation

---

## References

- [MCP Specification](https://modelcontextprotocol.io)
- [MCP SDK Python](https://github.com/modelcontextprotocol/python-sdk)
- [Flask-SocketIO](https://flask-socketio.readthedocs.io)
- [Termux Wiki](https://wiki.termux.com)

---

*Document Owner:* Development Team  
*Last Updated:* 2026-03-13  
*Review Cycle:* Weekly during implementation