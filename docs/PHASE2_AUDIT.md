# Phase 2 Audit: Tool Orchestration Engine

**Date:** 2026-03-13  
**Status:** Build Complete, Audit in Progress

---

## 1. Component Review

### 1.1 IntentDetector

| Aspect | Status | Notes |
|--------|--------|-------|
| Pattern-based detection | ✅ Implemented | 5 intent categories with regex patterns |
| Explicit command support | ✅ Implemented | `/imagine`, `/search`, `/weather`, etc. |
| LLM verification fallback | ✅ Stubbed | Returns preliminary if confidence >= 0.5 |
| Confidence scoring | ✅ Implemented | 0.0-1.0 based on match length |
| Parameter extraction | ✅ Implemented | Context-aware extraction per tool |

**Code Quality:**
- Clean separation of pattern compilation and execution
- Extensible `ToolIntent` enum for new intent types
- `_extract_params()` handles tool-specific parameter parsing

**Concerns:**
- Pattern list could become unwieldy as tools grow
- No caching of detection results
- LLM verification is stubbed (always accepts if >= 0.5)

---

### 1.2 ToolRouter

| Aspect | Status | Notes |
|--------|--------|-------|
| Internal tool routing | ✅ Implemented | Uses existing `execute_tool()` from registry |
| MCP routing | ⚠️ Stubbed | Connection and protocol not implemented |
| Timeout handling | ✅ Implemented | ThreadPoolExecutor with configurable timeouts |
| Execution tracking | ✅ Implemented | Database records for all executions |
| Error handling | ✅ Implemented | Catches and formats exceptions |

**Code Quality:**
- Good separation of concerns between `_execute_internal` and `_execute_mcp`
- Timeout configuration is externalized
- Database integration for audit trail

**Concerns:**
- MCP is fully stubbed - needs stdio and HTTP implementations
- No retry logic for transient failures
- Thread pool size is fixed at 4 workers
- No cancellation mechanism for long-running tools

---

### 1.3 ResultProcessor

| Aspect | Status | Notes |
|--------|--------|-------|
| Display type mapping | ✅ Implemented | IMAGE, WEATHER_CARD, SEARCH_RESULTS, etc. |
| Loading state generation | ✅ Implemented | Human-friendly loading messages |
| Error formatting | ✅ Implemented | User-friendly error messages |
| Narrative prompts | ✅ Implemented | LLM prompts for natural responses |
| Image path normalization | ✅ Implemented | Handles various path formats |

**Code Quality:**
- `TOOL_DISPLAY_CONFIG` centralizes tool behavior
- Clean format methods for each display type
- Good separation between technical and friendly error messages

**Concerns:**
- Image path logic assumes Flask static structure
- No validation of result structure before formatting
- `generate_narrative_prompt()` returns prompts, not actual narratives (by design)

---

## 2. Integration Points

### 2.1 Database Integration

```
IntentDetector → (no DB)
ToolRouter → ToolExecution records
ResultProcessor → (no DB, uses in-memory results)
```

**Status:** ToolRouter correctly creates and updates execution records.

### 2.2 Existing Tool Registry

```
ToolRouter._execute_internal() → tools.registry.execute_tool()
```

**Status:** Properly delegates to existing tool infrastructure.

### 2.3 MCP Integration (Planned)

```
ToolRouter._execute_mcp() → MCP connection → JSON-RPC call
```

**Status:** Stubs in place, needs:
- stdio subprocess management
- HTTP client implementation
- Connection pooling
- Reconnection logic

---

## 3. Test Coverage Simulation

### 3.1 Intent Detection Cases

| Test Case | Input | Expected Intent | Confidence |
|-----------|-------|-----------------|------------|
| TC1 | "Send me your picture" | IMAGE_GENERATE | >= 0.6 |
| TC2 | "/imagine a cat" | IMAGE_GENERATE | 1.0 |
| TC3 | "What's the weather?" | WEATHER | >= 0.6 |
| TC4 | "Search for Python docs" | WEB_SEARCH | >= 0.6 |
| TC5 | "What did we talk about yesterday?" | MEMORY_QUERY | >= 0.6 |
| TC6 | "Hello, how are you?" | NONE | 1.0 |
| TC7 | "Draw me something" | IMAGE_GENERATE | >= 0.5 |

### 3.2 Tool Routing Cases

| Test Case | Tool | Type | Expected Result |
|-----------|------|------|-----------------|
| TC8 | image_generate | internal | Image path returned |
| TC9 | unknown_tool | mcp (if configured) | Error or MCP call |
| TC10 | weather | internal | Weather data dict |

### 3.3 Result Processing Cases

| Test Case | Input | Display Type | Notes |
|-----------|-------|--------------|-------|
| TC11 | Image path string | IMAGE | Normalizes to web path |
| TC12 | Weather dict | WEATHER_CARD | Extracts all fields |
| TC13 | Search list | SEARCH_RESULTS | Limits to 5 results |
| TC14 | JSON dict | JSON | Pretty-formatted |
| TC15 | Error exception | ERROR | Friendly message |

---

## 4. Security Audit

| Check | Status | Notes |
|-------|--------|-------|
| Input validation | ⚠️ Partial | Patterns only, no sanitization |
| Timeout protection | ✅ Yes | All tools have timeouts |
| Database injection | ✅ Safe | Uses SQLAlchemy ORM |
| Path traversal | ⚠️ Partial | Image path normalization basic |
| MCP command injection | ⚠️ N/A | Not implemented yet |

---

## 5. Performance Audit

| Aspect | Status | Notes |
|--------|--------|-------|
| Pattern compilation | ✅ Cached | Compiled once at init |
| Thread pool | ✅ Bounded | 4 workers, queued execution |
| Database queries | ⚠️ Per-call | Could batch or cache |
| Result formatting | ✅ In-memory | No I/O in formatting |

---

## 6. Findings Summary

### Critical Issues (Must Fix)
1. **MCP Implementation Missing** - Fully stubbed, needs stdio/HTTP transport

### Major Issues (Should Fix)
2. **No Retry Logic** - Transient failures have no recovery
3. **No Cancellation** - Long tools can't be cancelled
4. **Basic Path Validation** - Image paths need stricter checks

### Minor Issues (Could Fix)
5. **Pattern List Growth** - Could use more structured approach
6. **No Detection Caching** - Repeated similar queries re-detect
7. **Fixed Thread Pool** - Could be dynamic based on load

### Positive Findings
- Clean architecture with clear separation of concerns
- Good database integration for audit trail
- Extensible design for new tools
- Proper error handling with user-friendly messages

---

## 7. Recommendations

### Before Phase 3 (UI)
1. Fix critical path validation in `_format_image_result()`
2. Add at least one MCP transport (stdio or HTTP)
3. Add retry logic with exponential backoff

### During Phase 3
4. Ensure UI components match display types in ResultProcessor
5. Test loading states with real tool execution

### After Phase 3
6. Add detection result caching
7. Implement cancellation mechanism
8. Add metrics/observability hooks

---

*Audit completed by: Development Team*  
*Next: Simulation Phase*
