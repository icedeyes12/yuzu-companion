# Tooling Refactor Roadmap

## Goal

Move Yuzu Companion from a hybrid legacy-command tool system to a clearer split:

- **standard function-calling tools** for atomic actions
- **skills** for multi-step workflows and orchestration

## Current state

The tool layer currently works, but it mixes several concerns:

- schema definition
- alias resolution
- dispatch
- validation
- markdown rendering
- legacy `/command` compatibility
- some tool-specific business logic

That is fine short-term, but it becomes expensive to maintain as the tool set grows.

## Progress so far

### Done
- richer tool metadata in `ToolDefinition`
- centralized argument validation
- normalized tool result shape
- canonical tool naming with aliases
- registry resolves aliases to canonical names
- registry returns canonical tool definitions only
- provider manager preserves OpenAI-compatible `tool_calls`
- app orchestration can consume structured `GenerateResult` tool calls

### Still in progress
- full removal of legacy `/command` parsing
- cleanup of direct command-specific assumptions inside `app.py`
- moving multi-step workflows into explicit skills
- docs/tests for the new tool contract

## Phase 1 — contract hardening

### Deliverables
- richer tool metadata in `ToolDefinition`
- centralized argument validation
- normalized tool result shape
- canonical tool naming with aliases

### Acceptance criteria
- every tool has a single canonical name
- every tool exposes a schema that can be converted to function calling
- validation happens before execution
- tools return a consistent structured result

## Phase 2 — registry cleanup

### Deliverables
- registry resolves aliases to canonical names
- registry stops duplicating tool definitions for aliases
- dispatcher returns normalized results only
- legacy string/markdown-only results are wrapped, not privileged

### Acceptance criteria
- one source of truth for tool lookup
- no duplicate tool schemas in the model-facing tools array
- existing callers still work

## Phase 3 — tool-by-tool simplification

### Memory tools
- keep `memory_search` focused on retrieval
- keep `memory_store` focused on persistence
- move any extra classification or formatting into helpers

### HTTP tools
- keep strict safety checks
- keep schemas explicit
- minimize freeform parsing

### Image tools
- keep generation focused on generation
- move config resolution and profile lookup into shared helpers where possible

## Phase 4 — introduce skills

Move any workflow that looks like a process rather than a primitive into a skill.

Good skill candidates:
- research and summarization flows
- memory curation flows
- multimodal analysis workflows
- integration pipelines with retries and branching

### Acceptance criteria
- skills are documented as workflows, not as fake single-function tools
- tools remain small and predictable
- orchestration lives in one place instead of being scattered across tool bodies

## Phase 5 — cleanup

- deprecate legacy `/command` parsing once callers are migrated
- remove duplicate compatibility branches
- document the final tool contract in `app/README.md`
- add tests for validation, alias resolution, and result normalization

## Implementation order

1. schema hardening
2. registry cleanup
3. update existing tools to declare categories, aliases, and safety notes
4. finish app/provider cleanup so structured tool calls are first-class everywhere
5. start carving out workflows into skills
6. remove legacy behavior only after coverage is stable
