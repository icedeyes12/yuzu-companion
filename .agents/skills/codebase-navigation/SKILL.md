---
name: codebase-navigation
description: Strict guidelines for navigating and modifying the yuzu-companion codebase. Use for refactoring, bug fixing, or feature implementation.
---
# Codebase Navigation Protocol

## Strict Workflow
1. **Never Assume**: Do not guess file content, architecture, or function signatures.
2. **Use Tools First**: Prioritize tool selection. You MUST use the `view_file` or `read_file` tool to inspect the target file *before* suggesting or writing any edits.
3. **Verify Context**: Search logs (e.g., `debug_logs/`) before proposing bug fixes. 
4. **Targeted Actions**: Optimize efficiency by using direct methods over broad, generalized searches.

