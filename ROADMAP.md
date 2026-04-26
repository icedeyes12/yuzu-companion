# Yuzu Companion — Roadmap

**Target**: Python 3.13+, PostgreSQL 18.2
**Updated**: 2026-04-26

---

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Legacy chat (`/api/send_message`) | ✅ Working | Persists to DB |
| Agentic chat (`/api/agentic/chat`) | ❌ Broken | **No persistence** |
| Frontend | ⚠️ Issue | Defaults to broken agentic endpoint |
| Database schema | ⚠️ Incomplete | Missing thinking/tool_calls columns |

---

## Phase 0: Research & Spike (1-2 days)

### Goals
- Validate LangGraph + PostgreSQL integration
- Test with existing providers (Chutes/Ollama)
- Verify Termux compatibility

### Tasks
1. Install dependencies
   ```bash
   pip install langgraph langgraph-checkpoint-postgres
   ```

2. Create proof-of-concept
   - Single agent with PostgresSaver
   - Test tool calling
   - Verify state checkpointing

3. Document findings

### Deliverables
- [ ] LangGraph spike code in `spikes/langgraph/`
- [ ] Compatibility report
- [ ] Performance benchmarks

---

## Phase 1: Schema Migration (1 day)

### Goals
- Add missing columns for agentic features

### Tasks
1. Create migration script
   ```sql
   -- migrations/003_add_agentic_columns.sql
   ALTER TABLE messages ADD COLUMN IF NOT EXISTS thinking TEXT;
   ALTER TABLE messages ADD COLUMN IF NOT EXISTS tool_calls JSONB DEFAULT '{}';
   ALTER TABLE messages ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
   
   CREATE INDEX IF NOT EXISTS idx_messages_tool_calls ON messages USING GIN(tool_calls);
   ```

2. Run migration on dev DB
3. Update models (`db_pg_models.py`)

### Deliverables
- [ ] Migration script
- [ ] Updated models
- [ ] Backward compatibility test

---

## Phase 2: LangGraph Integration (2-3 days)

### Goals
- Replace custom agentic loop with LangGraph
- Add proper persistence

### Tasks
1. Create LangGraph agent
   ```
   app/agents/
   ├── langgraph_agent.py      # Main agent
   ├── nodes/                   # Graph nodes
   │   ├── think.py            # Reasoning node
   │   ├── act.py              # Tool execution node
   │   └── observe.py          # Result analysis node
   └── state.py                # State definitions
   ```

2. Integrate PostgresSaver
   - Connection pooling
   - Checkpoint setup
   - State recovery

3. Wire tools
   - Local RPC tools
   - MCP tools
   - Hybrid dispatcher

### Deliverables
- [ ] LangGraph agent implementation
- [ ] Tool integration
- [ ] Persistence layer
- [ ] Unit tests

---

## Phase 3: Frontend Update (1 day)

### Goals
- Fix frontend endpoint selection
- Add agentic toggle UI

### Tasks
1. Add endpoint selection logic
   ```javascript
   // chat.js
   async handleChatMessage(text) {
       const useAgentic = this.agenticEnabled && this.needsTools(text);
       const endpoint = useAgentic 
           ? "/api/agentic/chat" 
           : "/api/send_message_stream";
       // ...
   }
   ```

2. Add agentic toggle
   - Sidebar toggle
   - Status indicator

3. Update SSE handling

### Deliverables
- [ ] Endpoint selector
- [ ] Agentic toggle UI
- [ ] SSE stream handler

---

## Phase 4: Testing & Documentation (1 day)

### Goals
- Ensure everything works
- Document new architecture

### Tasks
1. Unit tests
   - LangGraph checkpoint save/load
   - Tool calling
   - Persistence

2. Integration tests
   - Full conversation flow
   - Crash recovery
   - History retrieval

3. Update documentation
   - AGENTS.md
   - README.md
   - Architecture diagrams

### Deliverables
- [ ] Test suite
- [ ] Updated docs
- [ ] Troubleshooting guide

---

## Future Phases (Out of Scope)

### Phase 5: T-UI Refactor
- Replace `main.py` with Textual-based TUI
- Rich components
- Async input handling

### Phase 6: Advanced Features
- Multi-agent collaboration
- Tool marketplace
- Custom tool builder

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 0: Research | 1-2 days | ⏳ Pending |
| Phase 1: Schema | 1 day | ⏳ Pending |
| Phase 2: Integration | 2-3 days | ⏳ Pending |
| Phase 3: Frontend | 1 day | ⏳ Pending |
| Phase 4: Testing | 1 day | ⏳ Pending |
| **Total** | **6-8 days** | |

---

## Key Decisions Needed

1. **Agentic mode default?**
   - [ ] All chats use agentic (requires LangGraph migration first)
   - [ ] Opt-in via toggle (safer, incremental)

2. **Keep legacy endpoint?**
   - [ ] Yes, as fallback
   - [ ] No, migrate all to LangGraph

3. **Tool availability UI?**
   - [ ] Let user pick tools
   - [ ] All tools always available

---

## Dependencies

### Required
- `langgraph>=0.2.0`
- `langgraph-checkpoint-postgres`
- `httpx>=0.27.0` (already have)

### Optional
- `pydantic-ai` (for structured output validation)

---

## Success Metrics

### Before
```
Agentic persistence: 0%
History retrieval: 0%
Crash recovery: ❌
```

### After
```
Agentic persistence: 100%
History retrieval: 100%
Crash recovery: ✅
```
