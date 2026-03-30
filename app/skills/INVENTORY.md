# Skill Inventory

This file tracks workflows that are better expressed as skills than as atomic tools.

## Current skills

- `tool_synthesis.py` — post-tool natural-language follow-up after a tool result
- `session_naming.py` — session naming from recent conversation context
- `memory_summary.py` — session context summarization and episodic sync
- `memory_pipeline.py` — episodic extraction, semantic extraction, and decay
- `global_profile_summary.py` — long-form profile analysis across all sessions
- `memory_curation.py` — normalize, merge, dedupe, and parse profile-memory data
- `multimodal_review.py` — multimodal image intake, vision routing, and markdown image handling

## Good next candidates

- `tool_retry.py` — retry/branch logic for flaky external calls

## Rule of thumb

- If it does one action, keep it as a tool.
- If it needs multiple steps, retries, branching, or synthesis, make it a skill.
