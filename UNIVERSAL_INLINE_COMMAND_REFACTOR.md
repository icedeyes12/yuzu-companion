# Roadmap: Universal Inline Command + 2-Pass Synthesis Flow

> **Status:** APPROVED — Ready for Implementation
****Created:** 2026-05-12
****Target Version:** 3.1.0

---

## Executive Summary

Refactor tool execution dari **native provider tool calling** ke **universal inline** `/command` **+ 2-pass synthesis** untuk SEMUA tools.

### Goals

1. **Cross-provider portability** — Tidak ada dependency pada native tool calling API
2. **Stable context** — Tool results dalam format terstruktur (`role: "tools"`)
3. **Universal synthesis** — 2-pass SELALU terjadi setelah tool execution
4. **Clean DB sequence** — `user` → `assistant` → `tools` → `assistant`

### Non-Goals

- Tidak mengubah behavior frontend
- Tidak mengubah tool definitions (hanya output format)
- Tidak menambah tools baru

---

## 1. Current State Audit

### 1.1 Markdown Contract Dependencies

| File | Function | Current Behavior |
| --- | --- | --- |
|  | `build_tool_contract()` | Creates \`\`\`\`html-details |

🔧 tool_name...
\`\`\`\` |
| \`tools/schemas.py\` | \`ok_result()\` / \`error_result()\` | Wraps data in markdown contract |
| \`db_queries.py\` | \`extract_command_from_markdown_contract()\` | Parses \`/command\` from \`\`\`\`html-details
\` |
| \`db_queries.py\` | \`extract_raw_result_from_markdown_contract()\` | Strips \`\` formatting |
| \`db_queries.py\` | \`format_ai_history_rows()\` | Expands tool-role rows using extractors |
| \`orchestrator.py\` | \`\_persist_tool_result()\` | Stores markdown via \`get_tool_role()\` |
| \`registry.py\` | \`execute_tool()\` | Returns \`{"ok": ..., "markdown": "..."}\` |

### 1.2 Current Tool Result Storage

```markdown
Current DB Structure:
  messages.role = "image_tools" | "request_tools" | "memory_store_tools" | ...
  messages.content = "<details><summary>🔧 image_tools</summary>...
```"

Target DB Structure:
  messages.role = "tools"
  messages.content = "<tools><name>image_generate</name><result>...</result></tools>"
```

### 1.3 Current Tool Roles Map

```python
# db_queries.py
TOOL_ROLES = {
    "image_generate": "image_tools",
    "http_request": "request_tools",
    "memory_store": "memory_store_tools",
    "memory_search": "memory_search_tools",
}

ALL_TOOL_ROLES = set(TOOL_ROLES.values()) | {"memory_tools"}
```

### 1.4 Current Native Tool Call Path

```markdown
orchestrator.py:
  _parse_raw_tool_calls(provider_name, raw_response)
  _execute_tool_calls(tool_calls, session_id)
  
llm_client.py:
  _unique_tool_schemas() → tools[] array
  _send_to_provider(..., tools=schemas)
  
providers.py:
  parse_tool_calls(raw_response) → [{"name", "arguments", "id"}]
```

### 1.5 Current Terminal Tool Logic

```python
# registry.py
def is_terminal_tool(tool_name: str) -> bool:
    return tool_name in {"image_generate"}

# orchestrator.py
if is_terminal_tool(tool_name) and result.get("ok"):
    # Skip synthesis pass — tool result is final
else:
    # Run synthesis pass
```

### 1.6 Current Synthesis Pass Context

```python
# orchestrator.py
def _run_synthesis(profile, session_id, interface, tool_markdown, is_image_tool):
    # Context sent to LLM:
    # - Previous messages (including tool result as markdown)
    # - For image tools: base64 image attached
```

---

## 2. Target Architecture

### 2.1 New Execution Flow

```markdown
┌─────────────────────────────────────────────────────────────────────┐
│ 1. USER MESSAGE                                                     │
│    - Masuk ke orchestrator.py via handle_user_message()             │
│    - Store: messages(role="user", content=user_message)             │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. STREAMFILTER FIRST PASS                                          │
│    - LLM generates text + inline /command                            │
│    - StreamFilter detects /command mid-stream                        │
│    - Line-buffering: yield text immediately, buffer command lines   │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. TOOL DETECTION & EXECUTION                                       │
│    - Parse /command + args (supports multi-line args)               │
│    - execute_tool(name, args, session_id)                           │
│    - Truncate result if too large (prevent token overflow)          │
│    - Store: messages(role="assistant", content=first_pass_text)     │
│    - Store: messages(role="tools", content=<tools> XML)              │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. SECOND PASS (SYNTHESIS)                                          │
│    - Build context: user + assistant(first) + tools                 │
│    - LLM synthesizes narrative response                              │
│    - Store: messages(role="assistant", content=synthesis)           │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Differences from Current

| Aspect | Current | Target |
| --- | --- | --- |
| Tool invocation | Native provider tool calls OR `/command` detection | Universal `/command` inline |
| Tool result storage | Per-tool role (`image_tools`, etc.) + markdown | Single `tools` role + XML |
| Synthesis pass | Conditional (skip for terminal tools) | Always executed |
| Provider dependency | Yes (tool calling API) | No (pure text generation) |

---

## 3. Schema Strategy

### 3.1 New `role: "tools"` Format (XML-based)

```xml
<<tools>
  <name>image_generate</name>
  <status>ok</status>
  <data>
    <image_path>static/generated_images/20260512_cat.png</image_path>
    <model>hunyuan</model>
  </data>
  <error></error>
</tools>
```

### 3.2 XML Schema Definition

```markdown
<tools> ::= "<tools>" + <name> + <status> + [<data>] + [<error>] + "</tools>"
<name> ::= "<name>" + TOOL_NAME + "</name>"
<status> ::= "<status>" + ("ok" | "error") + "</status>"
<data> ::= "<data>" + (<key_value_pair>)* + "</data>"
<key_value_pair> ::= "<" + KEY + ">" + VALUE + "</" + KEY + ">"
<error> ::= "<error>" + ERROR_MESSAGE + "</error>"
```

### 3.3 XML Sanitization Rules

```python
# Full sanitization for XML safety
def sanitize_xml_value(value: str) -> str:
    """
    Handles:
    - XML entities: & → &amp;, < → &lt;, > → &gt;, " → &quot;, ' → &apos;
    - Invalid control characters (0x00-0x1F except 0x09, 0x0A, 0x0D): stripped
    - NULL bytes: removed
    """
```

### 3.4 Alternative: JSON-based Format (Backup Option)

```xml
<<tools>
{"name":"image_generate","status":"ok","data":{"image_path":"...","model":"hunyuan"},"error":null}
</tools>
```

---

## 4. Prompt Engineering

### 4.1 Tool Instructions for System Prompt

```markdown
# TOOL USAGE

You have access to tools. Use them by outputting commands in this format:

/imagine [description] — Generate an image
/request [URL] — Make an HTTP request  
/memory_store fact="[fact]" — Store a memory
/memory_search [query] — Search memories

## Rules:
1. Output /command on its own line
2. Continue conversational text after command
3. You will see the tool result and should acknowledge it naturally

## Example:
User: Can you make me a picture of a cat?
Assistant: Sure! Let me create that for you.
/imagine cute fluffy cat with big green eyes
I've generated the image for you. What do you think?
```

### 4.2 Synthesis Prompt Template

```markdown
# Current Context

You previously used a tool. Here's what happened:

<tool_result>
{TOOL_XML_RESULT}
</tool_result>

Now respond naturally to the user, acknowledging what the tool did.
Be conversational and brief.
```

### 4.3 Tools-to-Natural-Language Conversion

```python
def tool_definitions_to_prompt(tools: list[ToolDefinition]) -> str:
    """Convert TOOL_DEFINITION JSON schemas to natural language instructions."""
    lines = ["# Available Tools", ""]
    
    for tool in tools:
        # Extract tool name and description
        name = tool.name
        desc = tool.description
        
        # Build param list as natural language
        params_desc = []
        for param in tool.params:
            if param.required:
                params_desc.append(f"{param.name}: {param.description}")
            else:
                params_desc.append(f"{param.name} (optional): {param.description}")
        
        # Format as instruction
        lines.append(f"## /{name}")
        lines.append(f"{desc}")
        if params_desc:
            lines.append("Parameters:")
            for p in params_desc:
                lines.append(f"  - {p}")
        lines.append("")
    
    return "\n".join(lines)
```

---

## 5. Streaming Logic

### 5.1 Line-Buffering Strategy

```python
class StreamFilter:
    """
    Line-buffering approach:
    - Yield text immediately line-by-line
    - Buffer ONLY lines that START with '/'
    - On newline after '/': execute command, emit placeholder, continue
    
    This preserves typing effect while still catching commands.
    """
```

### 5.2 StreamFilter State Machine

```markdown
States:
  - NORMAL: yielding text immediately
  - COMMAND_DETECTED: found '/' at line start, buffering
  - COMMAND_EXECUTING: tool running, showing placeholder

Transitions:
  NORMAL → COMMAND_DETECTED: when line starts with '/'
  COMMAND_DETECTED → COMMAND_EXECUTING: when newline received
  COMMAND_EXECUTING → NORMAL: after tool completes
```

### 5.3 Streaming Output Example

```markdown
LLM Output:
"Baik, aku buatkan gambar kucing ya!
/imagine cute fluffy cat with big eyes
Semoga kamu suka gambarnya!"

StreamFilter yields:
1. "Baik, aku buatkan gambar kucing ya!\n"  ← immediate
2. {"type": "command_detected", "command": {...}}
3. [Tool execution - placeholder shown]
4. "Semoga kamu suka gambarnya!\n"  ← after tool
```

---

## 6. Multi-line Argument Handling

### 6.1 Supported Formats

```markdown
# Single-line positional
/imagine cute cat

# Single-line named args
/memory_store fact="User likes cats" category="Preferences"

# Multi-line quoted
/memory_store fact="This is a long fact
that spans multiple lines
until the closing quote" category="Identity"

# Multi-line JSON block
/request POST https://api.example.com
{
  "json": "payload",
  "multi": "line"
}
```

### 6.2 Argument Parsing Logic

```python
def parse_command_with_multiline_args(
    command_line: str,
    following_lines: list[str] | None = None
) -> dict:
    """
    Parse command including multi-line arguments.
    
    Supports:
    - Quoted strings (handles multi-line with re.DOTALL)
    - JSON blocks after newline
    - Single positional argument as default "prompt" key
    """
```

---

## 7. Token Overflow Prevention

### 7.1 Truncation Thresholds

```python
MAX_TOOL_RESULT_CHARS = 4000  # ~1000 tokens
MAX_TOOL_RESULT_LINES = 100
```

### 7.2 Tool-Specific Truncation

| Tool | Strategy |
| --- | --- |
| `http_request` | Truncate body, preserve headers & status |
| `memory_search` | Limit result count to 20 |
| `image_generate` | No truncation needed (path only) |
| `memory_store` | No truncation needed (small confirmation) |

### 7.3 Summarization for Very Large Results

```python
def summarize_large_result(data: dict, tool_name: str) -> str:
    """Generate brief summary when truncation still leaves too much context."""
    # HTTP: "HTTP 200 response (15000 chars). Key data extracted."
    # Memory: "Found 50 relevant memories. Top results shown."
```

---

## 8. Backward Compatibility

### 8.1 Dual-Path History Reader

```python
def format_ai_history_rows(rows: list[dict]) -> list[dict]:
    """
    Handle both old and new formats during transition:
    
    Old format:
      role = "image_tools" | "request_tools" | ...
      content = "```html-details
<summary>🔧 tool</summary>...
```"
    
    New format:
      role = "tools"
      content = "<tools>...</tools>"
    
    Both expand to:
      {role: "assistant", content: "/command args"}
      {role: "tools", content: result_data}
    """
    
    for row in rows:
        role = row.get("role", "")
        content = row.get("content", "")
        
        # New format detection
        if role == "tools" and content.startswith("<tools>"):
            # Parse XML format
            ...
        # Old format detection
        elif role in ALL_TOOL_ROLES:
            # Parse markdown contract
            ...
```

### 8.2 Transition Period

1. **Phase 1:** Deploy dual-path reader
2. **Phase 2:** Deploy new execution flow (new messages use XML)
3. **Phase 3:** Verify all new messages use XML
4. **Phase 4:** Remove markdown contract code

### 8.3 No Data Migration

- Old messages remain as-is (markdown format)
- New messages use XML format
- Dual-path reader handles both

---

## 9. Implementation Phases

### Phase 1: Infrastructure (Days 1-2)

**Files to modify:**

| File | Changes |
| --- | --- |
|  | Add `format_tool_result_xml()`, `sanitize_xml_value()` |
|  | Modify `execute_tool()` to return XML format |
|  | Add `TOOL_ROLE_UNIVERSAL = "tools"`, update `tool_role_for()` |
|  | Update `format_ai_history_rows()` for dual-path |

**Verification:**

- Unit tests for XML formatting
- Unit tests for sanitization
- Unit tests for dual-path history reader

### Phase 2: StreamFilter Refactor (Days 3-4)

**Files to modify:**

| File | Changes |
| --- | --- |
|  | Rewrite `StreamFilter` with line-buffering |
|  | Add `parse_command_with_multiline_args()` |

**Verification:**

- Unit tests for line-buffering
- Unit tests for multi-line arg parsing
- Integration test with mock LLM output

### Phase 3: Prompt Engineering (Day 5)

**Files to modify:**

| File | Changes |
| --- | --- |
|  | Add tool instructions section |
|  | Add synthesis prompt template |
|  | Remove `tools[]` array from provider calls |
|  | Remove native tool call parsing |

**Verification:**

- Manual testing with different providers
- Verify LLM outputs `/command` format

### Phase 4: Orchestrator Integration (Days 6-7)

**Files to modify:**

| File | Changes |
| --- | --- |
|  | Remove native tool call path |
|  | Implement 2-pass always synthesis |
|  | Update `_persist_tool_result()` |
|  | Add truncation layer |

**Verification:**

- End-to-end tests for all tools
- Token count verification
- DB sequence verification

### Phase 5: Cleanup (Day 8)

**Files to modify:**

| File | Changes |
| --- | --- |
|  | Remove `build_tool_contract()`, markdown helpers |
|  | Remove `extract_*_from_markdown_contract()` |
|  | Remove terminal tool logic |
|  | Remove tool call parsing methods |

**Verification:**

- All tests pass
- No markdown contract references remain
- No native tool call references remain

---

## 10. Testing Strategy

### 10.1 Unit Tests

```python
# tests/test_tool_xml_format.py
def test_xml_sanitization():
    assert sanitize_xml_value("a & b < c > d") == "a &amp; b &lt; c &gt; d"
    assert sanitize_xml_value("text\x00with\x1Fnulls") == "textwithnulls"

def test_xml_formatting():
    result = {"ok": True, "data": {"path": "/img.png"}}
    xml = format_tool_result_xml("image_generate", result)
    assert "<name>image_generate</name>" in xml
    assert "<status>ok</status>" in xml

# tests/test_stream_filter.py
def test_line_buffering():
    sf = StreamFilter()
    outputs = list(sf.feed("Hello\n/imagine cat\nBye\n"))
    assert outputs[0] == "Hello\n"
    assert outputs[1]["type"] == "command_detected"
    assert outputs[2] == "Bye\n"

def test_multiline_args():
    parsed = parse_command_with_multiline_args(
        '/memory_store fact="multi\nline" category="test"'
    )
    assert parsed["args"]["fact"] == "multi\nline"

# tests/test_dual_path_history.py
def test_old_format_parsing():
    row = {"role": "image_tools", "content": "```html-details
...
```"}
    formatted = format_ai_history_rows([row])
    assert formatted[0]["role"] == "assistant"

def test_new_format_parsing():
    row = {"role": "tools", "content": "<tools>...</tools>"}
    formatted = format_ai_history_rows([row])
    assert formatted[0]["role"] == "assistant"
```

### 10.2 Integration Tests

```python
# tests/test_inline_command_flow.py
def test_imagine_command_flow():
    """Full flow: user message → /imagine detection → tool exec → synthesis"""
    response = handle_user_message("Make me a cat picture", session_id=1)
    
    # Verify DB sequence
    messages = Database.get_session_messages(session_id=1)
    roles = [m["role"] for m in messages]
    assert roles == ["user", "assistant", "tools", "assistant"]

def test_request_truncation():
    """Large HTTP response is truncated"""
    # Mock large response
    result = execute_tool_with_truncation("http_request", {...})
    assert len(result["data"]["content"]) <= MAX_TOOL_RESULT_CHARS
```

### 10.3 Manual Testing Checklist

- [ ] Test with Ollama provider

- [ ] Test with Cerebras provider

- [ ] Test with OpenRouter provider

- [ ] Test with Chutes provider

- [ ] Verify streaming UX (typing effect preserved)

- [ ] Verify synthesis pass always happens

- [ ] Verify multi-line args work

- [ ] Verify large tool results truncated

- [ ] Verify old messages still readable

---

## 11. Rollback Plan

### 11.1 Feature Flags

```python
# app/config.py
USE_NATIVE_TOOL_CALLS = os.getenv("USE_NATIVE_TOOL_CALLS", "false").lower() == "true"
USE_MARKDOWN_CONTRACT = os.getenv("USE_MARKDOWN_CONTRACT", "false").lower() == "true"
```

### 11.2 Rollback Steps

1. Set `USE_NATIVE_TOOL_CALLS=true`
2. Set `USE_MARKDOWN_CONTRACT=true`
3. Restart service
4. New messages use old format
5. Old messages still readable (dual-path)

### 11.3 Metrics to Monitor

- Tool execution success rate
- Synthesis pass completion rate
- Average token count per turn
- Streaming latency
- Error rate by provider

---

## 12. File Change Summary

| File | Action | Lines Changed (Est.) |
| --- | --- | --- |
|  | Modify | +80 / -40 |
|  | Modify | +20 / -10 |
|  | Rewrite | +150 / -80 |
|  | Modify | +60 / -100 |
|  | Modify | +40 / -20 |
|  | Modify | +10 / -50 |
|  | Modify | +5 / -30 |
|  | Modify | +30 / -10 |
|  | Add/Modify | +200 |

**Total Estimated:** +595 / -340 lines

---

## 13. Dependencies

- No new Python packages required
- No database schema changes
- No frontend changes

---

## 14. Open Questions

1. **Command collision:** What if LLM outputs `/imagine` in a code block or quote?

   - *Proposed:* Only detect `/command` at line start after stripping leading whitespace

2. **Multiple commands in one response:** Should we support it?

   - *Proposed:* Yes, execute sequentially, single synthesis at end

3. **Tool result in synthesis:** Include full XML or summarized version?

   - *Proposed:* Include truncated XML, let LLM parse

---

## 15. References

- `file AGENTS.md` — Project architecture constraints
- `file tools/schemas.py` — Current tool definition schema
- `file orchestrator.py` — Current execution flow
- `file db_queries.py` — Current history formatting

---

*Document prepared for implementation approval.*