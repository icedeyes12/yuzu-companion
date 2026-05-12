# Roadmap: Universal Inline Command + 2-Pass Synthesis (v3.1.0)

> **Status:** 📋 PLANNING — Ready for implementation
> \*\***Version:** 3.1.0
> \*\***Last Updated:** 2026-05-12
> \*\***Branch:** `refactor/universal-inline-command` (to be created from `dev`)

---

## Executive Summary

Refactor tool execution from **dual-path** (native tool calls + inline `/command`) to **single universal inline path** with proper UX flow:

```markdown
User Message → LLM First Pass → Placeholder → Tool Execution → Result → Synthesis
```

### Goals

| Goal | Current | Target |
| --- | --- | --- |
| Tool invocation | Dual: native API calls + `/command` | Single: inline `/command` only |
| Tool result storage | Per-tool roles (`image_tools`, etc.) | Single `tools` role |
| Placeholder during execution | ❌ None | ✅ Immediate placeholder |
| First pass persistence | ❌ Not stored | ✅ Stored as `assistant` |
| UX flow | Silent during tool execution | Visible placeholder → result |

### Non-Goals

- No new tools
- No frontend rewrite (only add placeholder handling)
- No database schema changes

---

## Current Architecture Audit

### Files Involved

| File | Current Role | Changes Needed |
| --- | --- | --- |
|  | Dual-path execution, synthesis | Remove native path, add placeholder |
|  | `/command` detection, StreamFilter | Add XML parsing, placeholder emission |
|  | Markdown contract (`<details>`) | Add XML format, dual output |
|  | Tool dispatch | Add XML result formatting |
|  | Tool roles, history formatting | Add `tools` role, dual-path reader |
|  | Native tool call support | Remove tool call parsing |
|  | System prompt | Add tool instructions |
|  | LLM calls with tools\[\] | Remove tools\[\] parameter |
|  | Frontend | Add placeholder handling |

### Current Execution Flow

```markdown
┌─────────────────────────────────────────────────────────────────┐
│ handle_user_message() / handle_user_message_streaming()         │
└─────────────────────────────────────────────────────────────────┘
         │                                           │
         ▼                                           ▼
┌─────────────────────┐                 ┌─────────────────────┐
│ PATH 1: Native      │                 │ PATH 2: Inline      │
│ _parse_raw_tool_    │                 │ detect_command()    │
│ calls()             │                 │                     │
│ _execute_tool_      │                 │ execute_command()   │
│ calls()             │                 │                     │
└─────────────────────┘                 └─────────────────────┘
         │                                           │
         └─────────────────┬─────────────────────────┘
                           ▼
              _persist_tool_result()
                           │
                           ▼
              _run_synthesis() / _stream_synthesis()
```

### Problems Identified

| \# | Problem | Impact |
| --- | --- | --- |
| 1 | Dual execution paths | Complexity, drift risk |
| 2 | No placeholder during tool execution | Silent UX gap |
| 3 | First pass not stored | Incomplete history |
| 4 | Per-tool roles (`image_tools`, etc.) | Inconsistent storage |
| 5 | Markdown contract only | No structured data for synthesis |

---

## Target Architecture

### New Execution Flow

```markdown
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER MESSAGE                                                 │
│    Database.add_message("user", message)                        │
└─────────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. LLM FIRST PASS (streaming)                                   │
│    "Baik, saya akan mencari memori tentang kucing..."           │
│    <tools>                                                      │
│      <name>memory_search</name>                                 │
│      <args><query>cats</query></args>                           │
│    </tools>                                                     │
└─────────────────────────────────────────────────────────────────┘
                           │
                           │ StreamFilter detects <tools>
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. EMIT PLACEHOLDER (immediate)                                 │
│    yield {"type": "tool_executing", "name": "memory_search",    │
│           "args": {"query": "cats"}}                            │
│    Frontend shows: 🔧 memory_search ⏳ Executing...             │
└─────────────────────────────────────────────────────────────────┘
                           │
                           │ Continue streaming first pass
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. STORE FIRST PASS                                             │
│    Database.add_message("assistant", first_pass_text)           │
│    (includes acknowledgment + <tools> block)                    │
└─────────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. EXECUTE TOOL                                                 │
│    result = execute_tool("memory_search", {"query": "cats"})    │
│    xml_result = format_tool_result_xml(result)                  │
└─────────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. EMIT RESULT (replace placeholder)                            │
│    yield {"type": "tool_result", "status": "ok",                │
│           "xml": "<tools>...</tools>"}                          │
│    Frontend updates placeholder: ✓ Found 3 memories             │
└─────────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. STORE TOOL RESULT                                            │
│    Database.add_message("tools", xml_result)                    │
└─────────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. SECOND PASS (synthesis)                                      │
│    Context: user + assistant(first) + tools                     │
│    LLM generates natural response                               │
│    Stream synthesis to frontend                                  │
└─────────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. STORE SYNTHESIS                                              │
│    Database.add_message("assistant", synthesis_text)            │
└─────────────────────────────────────────────────────────────────┘
```

### DB Message Sequence

| Step | Role | Content |
| --- | --- | --- |
| 1 | `user` | "Search my memories about cats" |
| 2 | `assistant` | "Baik, saya akan mencari...\\n..." |
| 3 | `tools` | `<tools><name>memory_search</name>...</tools>` |
| 4 | `assistant` | "Saya menemukan 3 memori tentang kucing..." |

---

## Implementation Phases

### Phase 1: Infrastructure — XML Format & Storage

**Goal:** Add XML formatting and universal storage role.

**Files to modify:**

| File | Changes | Status |
| --- | --- | --- |
|  | Add `sanitize_xml_value()`, `format_tool_result_xml()`, `dual_format_result()` | ✅ Done |
|  | Add `TOOL_ROLE_UNIVERSAL`, update `tool_role_for()` | ✅ Done |

**Tasks:**

- [x]   Add `sanitize_xml_value()` to `file tools/schemas.py`

  - [x]   XML-escape: `< > & " '`

  - [x]   Remove NULL bytes

  - [x]   Remove control chars (except tab, newline, CR)

  - [x]   Unit tests

- [x]   Add `format_tool_result_xml()` to `file tools/schemas.py`

  - [x]   Output: `<tool_result><name>...</name><status>...</status>...</tool_result>`

  - [x]   Handle ok/error status

  - [x]   Handle nested dict/list data

  - [x]   Limit list items to 20

  - [x]   Unit tests

- [x]   Add `dual_format_result()` to `file tools/schemas.py`

  - [x]   Return both `markdown` and `xml` formats

  - [x]   Backward compatible with existing `ok_result()` / `error_result()`

  - [x]   Unit tests

- [x]   Add `TOOL_ROLE_UNIVERSAL = "tools"` to `file database/db_queries.py`

  - [x]   Constant defined

  - [x]   Exported in `__all__`

  - [x]   Unit test

- [x]   Update `tool_role_for()` to support `use_universal` flag

  - [x]   Default behavior unchanged (backward compat)

  - [x]   `use_universal=True` returns `"tools"`

  - [x]   Unit tests

- [x]   Create test file `file tests/test_v31_phase1.py`

  - [x] 16 tests, all passing

**Verification:**

```bash
python -m py_compile app/tools/schemas.py app/database/db_queries.py
ruff check .
python -m pytest tests/test_v31_phase1.py -v
# Expected: 16 passed
```

**Commit:** `feat(tools): Phase 1 - XML formatting and universal storage role`

---

### Phase 2: Registry — Dual Output Format

**Goal:** Tools return both XML and markdown for backward compatibility.

**Files:**

- [x]   `file app/tools/registry.py` — Update `execute_tool()` return format

- [x]   `file app/tools/schemas.py` — Update `ok_result()`, `error_result()` to include xml

**Tasks:**

- [x]    2.1 Update `execute_tool()` return format

  - [x]   Return: `{"ok": bool, "data": dict, "markdown": str, "xml": str}`

  - [x]   `xml` is new, `markdown` is kept for backward compat

- [x]    2.2 Update `ok_result()` and `error_result()` in schemas

  - [x]   Both now include `xml` field using `format_tool_result_xml()`

  - [x]   Backward compatible with existing callers

- [x]    2.3 Verify all tools return dual format

  - [x]   `file image_generate.py` — uses `ok_result()`/`error_result()` ✅

  - [x]   `file http_request.py` — uses `ok_result()`/`error_result()` ✅

  - [x]   `file memory_store.py` — uses `ok_result()`/`error_result()` ✅

  - [x]   `file memory_search.py` — uses `ok_result()`/`error_result()` ✅

- [x]    2.4 Registry handles legacy tools

  - [x]   If tool returns dict without `xml`, registry adds it

  - [x]   If tool returns string (legacy), registry wraps with xml

- [x]    2.5 Write tests

  - [x]   `test_ok_result_has_xml()`

  - [x]   `test_error_result_has_xml()`

  - [x]   17 tests, all passing

**Verification:**

```bash
python -m pytest tests/test_v31_phase1.py -v
# Expected: 17 passed
ruff check .
```

**Commit:** `feat(registry): Phase 2 - Dual output format (XML + markdown)`

---

### Phase 3: StreamFilter — XML Parsing & Placeholder Emission

**Goal:** StreamFilter detects `<tools>`, emits placeholder, extracts tool call.

**Files:**

- [x] `file app/commands.py` — Rewrite `StreamFilter`

**Tasks:**

- [x]  3.1 Add `StreamState` enum

  - [x] `NORMAL` — yielding text immediately

  - [x] `TOOLS_DETECTED` — buffering `<tools>` block

  - [x] `TOOLS_COMPLETE` — `<tools>` block parsed, ready to emit

- [x]  3.2 Add XML parsing patterns

  - [x] `_TOOLS_BLOCK_PATTERN` — regex to match `<tools>...</tools>`

  - [x] `_parse_tools_block()` — extract name, args from XML

- [x]  3.3 Rewrite `StreamFilter.feed()`

  - [x] Character-by-character processing

  - [x] Detect `<tools>` opening tag

  - [x] Buffer until `</tools>` closing tag

  - [x] On complete block: emit placeholder dict, store parsed tool call

  - [x] Yield text before/after tools block immediately

  - [x] Legacy `/command` detection at stream start (backward compat)

- [x]  3.4 Add `StreamFilter.tool_call` property

  - [x] Returns `{"name": str, "args": dict}` after detection

  - [x] Returns `None` if no tool detected

- [x]  3.5 Add `StreamFilter.flush()`

  - [x] Handle incomplete tools block at stream end

  - [x] Return any buffered text

  - [x] Handle legacy `/command` without newline

- [x]  3.6 Write unit tests

  - [x] `test_normal_text_yields_immediately()`

  - [x] `test_tools_block_detected()`

  - [x] `test_tools_block_emits_placeholder()`

  - [x] `test_text_after_tools_yields()`

  - [x] `test_incomplete_tools_block_flush()`

  - [x] `test_legacy_command_detected()`

  - [x] 26 tests, all passing

**Verification:**

```bash
python -m pytest tests/test_v31_phase3.py -v
# Expected: 26 passed
ruff check app/commands.py
```

**Commit:** `feat(commands): Phase 3 - StreamFilter XML parsing & placeholder`

---

### Phase 4: Orchestrator — Single Path Flow

**Goal:** Remove native tool call path, implement single inline path with placeholder.

**Files:**

- [x] `file app/orchestrator.py` — Major refactor

**Tasks:**

- [x]    4.1 Remove native tool call functions

  - [x]   Delete `_parse_raw_tool_calls()`

  - [x]   Delete `_execute_tool_calls()`

  - [x]   Remove `tool_calls` handling in `handle_user_message()`

- [x]    4.2 Update `handle_user_message_streaming()` flow

  - [x]   Remove native tool call branch

  - [x]   After stream ends, check `sf.tool_call`

  - [x]   If tool detected:

    - [x]   Store first pass: `Database.add_message("assistant", first_pass_text)`

    - [x]   Emit placeholder event (already done by StreamFilter)

    - [x]   Execute tool

    - [x]   Emit result event

    - [x]   Store tool result: `Database.add_message("tools", xml_result)`

    - [x]   Run synthesis

    - [x]   Store synthesis: `Database.add_message("assistant", synthesis_text)`

  - [x]   If no tool:

    - [x] Store response: `Database.add_message("assistant", text)`

- [x]    4.3 Update `_persist_tool_result()` signature

  - [x]   Accept `xml: str` parameter

  - [x]   Use `TOOL_ROLE_UNIVERSAL` for storage role

- [x]    4.4 Add synthesis context builder

  - [x]   Include first pass text in context

  - [x]   Include tool result XML

- [x]    4.5 Remove `tools[]` array from LLM calls

  - [x] Verify `generate_ai_response_streaming()` doesn't pass tools

- [x]    4.6 Write integration tests

  - [x]   `test_tool_execution_flow()` — full flow with DB verification (marked as skip - needs DB)

  - [x]   `test_no_tool_flow()` — plain response

  - [x]   `test_synthesis_after_tool()` — verify synthesis happens

**Verification:**

```bash
python -m pytest tests/test_v31_phase4.py -v
ruff check app/orchestrator.py
```

**Commit:** `feat(orchestrator): Phase 4 - Single path flow with placeholder`

---

### Phase 5: Providers — Remove Tool Call Support

**Goal:** Clean up providers, remove native tool call parsing.

**Files:**

- [x]   `file app/providers.py` — Remove tool call methods

- [x]   `file app/llm_client.py` — Remove tools[] parameter

**Tasks:**

- [x]    5.1 Remove `parse_tool_calls()` from `AIProvider` base class

  - [x] Delete method and all overrides

- [x]    5.2 Remove `tools` parameter handling in providers

  - [x]   `OpenRouterProvider.send_message()` — remove `tools = kwargs.get('tools')`

  - [x]   `ChutesProvider.send_message()` — remove tools from payload

  - [x]   Other providers as needed

- [x]    5.3 Update `file llm_client.py`

  - [x]   Remove `_unique_tool_schemas()` (kept for registry)

  - [x]   Remove `tools=schemas` from `_send_to_provider()` calls

- [x]    5.4 Remove native tool call references in docstrings

  - [x] Update `AIProvider.send_message()` docstring

- [x]    5.5 Write regression tests

  - [x]   Verify providers still work without tools parameter

  - [x]   Test with multiple providers (Ollama, OpenRouter, Chutes)

**Verification:**

```bash
python -m pytest tests/test_v31_phase1.py tests/test_v31_phase3.py tests/test_v31_phase4.py -v
ruff check app/providers.py app/llm_client.py
```

**Commit:** `feat(providers): Phase 5 - Remove native tool calling`

---

### Phase 6: Prompts — Tool Instructions

**Goal:** Add inline command documentation to system prompt.

**Files:**

- [x] `file app/prompts.py` — Add tool instructions

**Tasks:**

- [x]    6.1 Add tool instructions section to system prompt

  - [x]   Document each available tool with `/command` syntax

  - [x]   Examples: `/imagine cat`, `/memory_search query`

  - [x]   Format rules: command on its own line

- [x]    6.2 Add synthesis prompt template

  - [x]   Template for second pass context

  - [x]   Include tool result XML

  - [x]   Instruction to acknowledge naturally

- [x]    6.3 Remove tools\[\] array construction

  - [x] Verify no `get_tool_definitions()` call for LLM context

- [x]    6.4 Write manual tests

  - [x]   Verify LLM outputs `/command` format

  - [x]   Test with different providers

**Verification:**

```bash
python -c "from app.prompts import build_system_message; print(build_system_message({'display_name': 'Test', 'partner_name': 'Yuzu'}, '')[:500])"
ruff check app/prompts.py
```

**Commit:** `feat(prompts): Phase 6 - Add inline tool instructions`

---

### Phase 7: Frontend — Placeholder Handling

**Goal:** Frontend shows placeholder during tool execution.

**Files:**

- [ ]   `file static/js/chat.js` — Add placeholder handling

- [ ]   `file static/css/chat.css` — Placeholder styles

**Tasks:**

- [ ]    7.1 Add placeholder message type

  - [ ]   `addMessage("tool_executing", data)` — shows loading state

  - [ ]   `updateToolMessage(id, result)` — replaces placeholder with result

- [ ]    7.2 Handle streaming events

  - [ ]   Parse `{"type": "tool_executing", ...}` from stream

  - [ ]   Show placeholder immediately

  - [ ]   Parse `{"type": "tool_result", ...}` from stream

  - [ ]   Replace placeholder with result

- [ ]    7.3 Add placeholder styles

  - [ ]   `.tool-placeholder.executing` — loading spinner

  - [ ]   `.tool-placeholder.success` — checkmark, collapsible details

  - [ ]   `.tool-placeholder.error` — error icon, message

- [ ]    7.4 Handle old `<details>` format (backward compat)

  - [ ]   Detect `<details>` in message

  - [ ]   Render as collapsible block (existing behavior)

- [ ]    7.5 Write manual tests

  - [ ]   Test `/imagine` — shows placeholder, then image

  - [ ]   Test `/memory_search` — shows placeholder, then results

  - [ ]   Test tool error — shows error in placeholder

**Verification:**

```bash
# Manual: Open browser, test tool commands
ruff check static/js/chat.js  # if applicable
```

**Commit:** `feat(frontend): Phase 7 - Placeholder handling`

---

### Phase 8: Cleanup & Migration

**Goal:** Remove old code, update documentation.

**Files:**

- [ ]   All files — Final cleanup

- [ ]   `docs/roadmap-history/` — Archive roadmap

**Tasks:**

- [ ]    8.1 Remove markdown contract helpers (optional)

  - [ ]   Consider keeping for backward compat

  - [ ]   Or remove `build_tool_contract()` if sure all old data migrated

- [ ]    8.2 Update `file AGENTS.md`

  - [ ]   Document new tool execution flow

  - [ ]   Update architecture diagram

  - [ ]   Add rules for tool development

- [ ]    8.3 Move roadmap to history

  - [ ] `mv UNIVERSAL_INLINE_COMMAND_REFACTOR.md docs/roadmap-history/`

- [ ]    8.4 Final verification

  - [ ]   All tests pass

  - [ ]   Ruff clean

  - [ ]   Manual testing with all providers

- [ ]    8.5 Merge PR

  - [ ]   Squash commits or keep separate

  - [ ]   Update CHANGELOG.md

**Verification:**

```bash
python -m pytest tests/ -v
ruff check .
git status
```

**Commit:** `docs: Phase 8 - Cleanup and finalize v3.1.0`

---

## Risk Mitigation

### Rollback Points

| Phase | Rollback Command |
| --- | --- |
| After Phase 1 | `git revert HEAD` |
| After Phase 2 | `git revert HEAD~2` |
| After Phase 3 | `git revert HEAD~3` |
| After Phase 4+ | Feature flag: `USE_LEGACY_TOOL_PATH=true` |

### Feature Flags (Optional)

```python
# app/config.py
USE_UNIVERSAL_TOOL_PATH = os.getenv("USE_UNIVERSAL_TOOL_PATH", "true").lower() == "true"
```

### Backward Compatibility

| Aspect | Strategy |
| --- | --- |
| Old messages in DB | Dual-path reader handles both formats |
| Frontend | Handles both `<details>` and `<tools>` |
| Tool results | Returns both `markdown` and `xml` fields |

---

## Testing Checklist

### Unit Tests

- [ ]   `file test_tool_xml_format.py` — XML sanitization, formatting

- [ ]   `file test_stream_filter.py` — XML detection, placeholder emission

- [ ]   `file test_orchestrator.py` — Full flow, DB persistence

- [ ]   `file test_registry.py` — Dual output format

### Integration Tests

- [ ]   Test with Ollama provider

- [ ]   Test with OpenRouter provider

- [ ]   Test with Chutes provider

- [ ]   Test with Cerebras provider

### Manual Tests

- [ ]   `/imagine cat` — image generation

- [ ]   `/memory_search cats` — memory search

- [ ]   `/memory_store fact="test"` — memory storage

- [ ]   `/request https://example.com` — HTTP request

- [ ]   Tool error handling — network timeout, invalid args

---

## Timeline Estimate

| Phase | Duration | Dependencies |
| --- | --- | --- |
| Phase 1 | 1 day | None |
| Phase 2 | 1 day | Phase 1 |
| Phase 3 | 1-2 days | Phase 1 |
| Phase 4 | 2 days | Phase 2, 3 |
| Phase 5 | 0.5 day | Phase 4 |
| Phase 6 | 0.5 day | Phase 4 |
| Phase 7 | 1 day | Phase 4 |
| Phase 8 | 0.5 day | All phases |

**Total:** \~7-9 days

---

## Success Criteria

- [ ]   All tests pass

- [ ]   Ruff check clean

- [ ]   Manual testing with all providers successful

- [ ]   No regression in existing functionality

- [ ]   Placeholder shown during tool execution

- [ ]   Tool results stored as `tools` role

- [ ]   Synthesis pass always runs after tool execution

- [ ]   Frontend displays tool results correctly

---

## References

- `file yuzu-companion/AGENTS.md` — Project architecture
- `file yuzu-companion/app/orchestrator.py` — Current execution flow
- `file yuzu-companion/app/commands.py` — Current StreamFilter
- `file yuzu-companion/app/tools/schemas.py` — Current tool schema
- `file yuzu-companion/app/database/db_queries.py` — Current tool roles

---

*Document prepared for implementation approval.*