# Tooling Refactor Roadmap

## Goal

Move Yuzu Companion from a hybrid legacy-command tool system to a clearer split:

- **standard function-calling tools** for atomic actions
- **skills** for multi-step workflows and orchestration

## Final state

The tooling layer now follows a cleaner shape:

- tool definitions are canonical and schema-driven
- aliases resolve to canonical tool names
- validation happens before execution
- tool results are normalized
- multimodal and summary workflows live in skills
- legacy `/command` parsing has been removed from the app flow

## Completed work

### Tooling core
- richer tool metadata in `ToolDefinition`
- centralized argument validation
- normalized tool result shape
- canonical tool naming with aliases
- registry resolves aliases to canonical names
- registry returns canonical tool definitions only
- provider manager preserves OpenAI-compatible `tool_calls`
- app orchestration consumes structured `GenerateResult` tool calls

### Tool-by-tool simplification
- `http_request`: simplified argument handling, added explicit `body` support, tightened dispatch
- `image_generate`: cleaned duplicate profile lookup and unused imports
- `memory_search`: kept focused on retrieval
- `memory_store`: kept focused on persistence

### Skill extraction
- multimodal routing now goes through `run_multimodal_review`
- global profile summary lives behind `run_global_profile_summary`
- memory workflows remain skill-based (`run_memory_pipeline`, `run_memory_summary`)
- tools stay atomic; orchestration lives in skill helpers

### Cleanup and verification
- legacy `/command` parsing removed from the app flow
- duplicate compatibility branches removed where possible
- README updated to describe the current tool contract
- smoke tests added for registry/tool-contract behavior
- `ruff check` and test suite pass

## Current architecture rules

- tools should do one thing well
- skills should own multi-step workflows
- the registry is the single source of truth for dispatch
- app-level orchestration should stay thin and predictable

## Suggested future work

- keep adding tests as new tools are introduced
- move any future multi-step flow into a skill instead of growing `app.py`
- keep docs aligned with the actual runtime behavior
