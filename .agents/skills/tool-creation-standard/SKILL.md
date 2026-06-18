---
name: tool-creation-standard
description: Standards for defining, registering, and returning tool results in yuzu-companion. Use when adding or modifying tools under app/tools/ and registry dispatch.
compatibility: Created for Zo Computer
metadata:
  author: yuzu.zo.computer
---

# Tool Creation Standards

## Scope
Covers the tool contract used by `file 'app/tools/registry.py'`, `file 'app/tools/schemas.py'`, and the modules in `file 'app/tools/'`. About tool definition, dispatch, schema generation, and result formatting. Does not override the base constitutions.

## 1. Canonical Single-Tool Module
Reference implementation: `file 'app/tools/memory_search.py`. A single-tool module exposes:
- `TOOL_DEFINITION = ToolDefinition(name=..., description=..., role="<name>_tools", parameters=[ToolParam(...)], needs_session=..., is_terminal=...)`
- `async def execute(arguments, **kwargs)` — pull `session_id` and `tool_name` out of `kwargs`. Async is preferred; sync is supported (the dispatcher wraps sync `execute` in `asyncio.to_thread`).
- Returns via `ok_result(data, TOOL_DEFINITION, full_command, partner_name)` or `error_result(message, TOOL_DEFINITION, full_command, partner_name)` from `file 'app/tools/schemas.py'`.

## 2. Definition Registration
- All definitions are collected lazily by `_collect_definitions()` in `file 'app/tools/registry.py'`. A tool that is not registered there is unreachable.
- `_load_tool_module(tool_name)` must also map the tool name (and any alias) to its module so dispatch can lazy-import it.
- Aliases are registered explicitly (e.g. `imagine` → `image_generate`, `request` → `http_request`). Add an alias only when there is a real user-facing reason; otherwise keep one name.

## 3. Three Definition-Exposure Conventions
The registry supports three module shapes; pick the one that matches your tool:
1. **Single definition** — `TOOL_DEFINITION = ToolDefinition(...)` (most tools).
2. **Multiple definitions in one module** — expose `TOOL_READ`, `TOOL_WRITE`, ... and a default `TOOL_DEFINITION = TOOL_READ`. The module's `execute(arguments, session_id=None, **kwargs)` must branch on `kwargs.get("tool_name")` to route to the right `execute_<op>` (see `file 'app/tools/fs_operations.py'`).
3. **Dict of definitions** — `TOOL_DEFINITION = {"bash": TOOL_BASH}` for modules that bundle several named tools under one dispatch key (see `file 'app/tools/shell_exec.py'`).

## 4. Result Contract
- New tools must return `{"ok": True, "data": {...}, "markdown": ...}` or `{"ok": False, "error": "...", "markdown": ...}`.
- `markdown` is produced by `build_tool_contract()`, which emits a **`<tools>...</tools>`** block (not `<details>`). That block is the only format stored in the DB and rendered by the frontend.
- Do not return raw strings or raw markdown from `execute()`. The dispatcher has a legacy fallback that wraps old `<details>`-prefixed strings, but new tools must not rely on it.
- `data` is flattened into the markdown contract by `_flatten_lines`; use a `content` key with `file_ext` for fenced code blocks, and prefix string values with `<` for raw HTML pass-through (e.g. `<img ...>`).

## 5. Schemas
- Use `ToolParam` and `ToolDefinition` dataclasses from `file 'app/tools/schemas.py'`. `ToolDefinition.to_llm_schema()` is the only serializer — never hand-build the OpenAI function schema.
- `is_terminal=True` means a successful result skips the second synthesis LLM pass (`image_generate`, `memory_search`). Default `False`.
- `needs_session=True` means the dispatcher auto-injects `session_id` into `arguments` if missing.

## 6. Dispatch Invariants
- `execute_tool(tool_name, arguments, session_id)` in `registry.py` is the **single** dispatch point. No business logic calls tool modules directly.
- Tool modules are lazy-imported; never import them at the top of `registry.py`.
- Tool errors and load failures are currently logged at INFO; when you touch a tool, prefer `logger.warning` / `logger.error` for failures so they surface.

## Anti-Patterns
- Do not register a "tool" that is actually a library. `file 'app/tools/multimodal.py'` is a library (exposes the `multimodal_tools` singleton, no `TOOL_DEFINITION`/`execute`); it is imported as `from app.tools.multimodal import multimodal_tools`, never dispatched.
- Do not leave a `_load_tool_module` branch for a name that is not registered in `_collect_definitions()` — it is unreachable dead code.
- Do not hand-roll the LLM schema or store `<details>` blocks from new tools.
