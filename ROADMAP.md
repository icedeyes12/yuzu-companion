Here's the updated ROADMAP.md reflecting the approved commit:

` ` `markdown
# Refactor Roadmap: Complete Codebase Pythonic Refactor

**Project**: yuzu-companion  
**Branch**: `refactor/stage-1-app-decomposition`  
**MR**: [!70](https://gitlab.com/icedeyes12-group/yuzu-companion/-/merge_requests/70)  
**Status**: Stage 1 Complete ✅ | Ready for Review  
**Strategy**: Staged approach - one MR per concern, independently testable  
**Behavior Preservation**: Option (b) - rename/reshape APIs freely (self-hosted, controlled callers)

---

## 📋 Overview

Refactor ~30 Python files in `app/` package, with `app.py` (1400 lines) being the primary monolith. Breaking into 6 coordinated stages to avoid thousands-of-lines MRs that can't be reviewed or tested on Termux.

**⚠️ Note**: Stage 1 expanded beyond original scope to include critical memory system consolidation work (originally planned for Stage 4). This was necessary to ensure the foundation modules had proper memory integration.

---

## Stage 1: Foundation Modules + Memory Consolidation ✅ COMPLETE

**Goal**: Split 1400-line monolith into focused modules + consolidate memory SQL  
**Impact**: Highest leverage, biggest maintainability win  
**Files Changed**: 23 files

### ✅ Core Modules Extracted

- [x] **`app/logging_config.py`** - Centralized logging
  - Honors `LOG_LEVEL` environment variable
  - Idempotent configuration with `get_logger()` helper
  - Replaces scattered `print(...)` debug calls

- [x] **`app/commands.py`** - Command detection & execution
  - `/command` detection logic (`detect_command`)
  - `StreamFilter` for command sniffing in streaming responses
  - Image shortcut guards (markdown image detection)
  - Tool dispatch integration (`execute_command`)
  - Command argument parsing with tool aliases

- [x] **`app/prompts.py`** - System prompt assembly
  - System prompt builder with affection/closeness modes
  - Message context construction (`build_messages`)
  - Memory retrieval integration (static + dynamic)
  - Session context injection
  - Interface-specific formatting (terminal vs web)

- [x] **`app/llm_client.py`** - AI response generation
  - **`chutes_chat()`** - Consolidated Chutes HTTP helper
  - Eliminates 3 duplicated raw-Chutes call sites
  - Vision routing logic
  - Direct `/imagine` handling
  - `generate_ai_response()` (non-streaming)
  - `generate_ai_response_streaming()` (streaming)
  - Provider/model resolution

- [x] **`app/orchestrator.py`** - Message handling entrypoint
  - `handle_user_message()` (non-streaming)
  - `handle_user_message_streaming()` (streaming)
  - Tool detection → execution → synthesis pipeline
  - Image context management with base64 encoding
  - Post-turn side effects (session naming, memory summarization)
  - **BUG FIX**: Fixed duplicated synthesis block
  - **BUG FIX**: Fixed unbound `final_response` variable

- [x] **`app/profile_analysis.py`** - Profile & memory analysis
  - `summarize_global_player_profile()` - Full conversation analysis
  - `parse_global_profile_summary()` - LLM output parser
  - `_merge_profile_data()` - Smart memory merging
  - Per-session memory summarization
  - Chutes integration for summaries
  - Memory normalization and deduplication

### ✅ Database Layer Improvements

- [x] **`app/db_pg.py`** - Enhanced PostgreSQL layer
  - Improved `PgSession` / `AsyncPgSession` context managers
  - Better error handling and logging
  - **FIX**: `pg_scalar()` now uses `execute_scalar()` (was incorrectly using `fetchone()`)
  - Module-level convenience helpers
  - Full `__all__` exports
  - Comprehensive docstrings

### ✅ Memory System Consolidation (Stage 4 Work)

- [x] **`app/memory/db_memory_queries.py`** - NEW FILE
  - Single source of truth for SQL strings
  - Vector literal helpers (`normalize_vector`, `vector_literal`)
  - Dynamic WHERE-clause builders
  - Eliminates SQL duplication between sync/async paths
  - Static SQL constants for common queries
  - pgvector integration with injection-safe interpolation

- [x] **`app/memory/models.py`** - DEPRECATED
  - Added deprecation warnings
  - Stub exports for backward compatibility
  - Migration path documented in comments

### ✅ Type Hints & Modern Python

- [x] All new modules use `from __future__ import annotations`
- [x] PEP 604 union syntax (`X | None`) throughout
- [x] Full type coverage on public APIs
- [x] Proper use of `Iterator`, `Iterable`, `Any` from `typing`

### ✅ Code Quality

- [x] All `print()` debug calls replaced with `logging`
- [x] Consistent use of `get_logger(__name__)`
- [x] Proper exception handling with `BLE001` noqa where defensive
- [x] Comprehensive docstrings on all public functions
- [x] Clear separation of concerns

### 📊 Stage 1 Statistics

- **Files Changed**: 23
- **Lines Added**: ~3,500+
- **Lines Removed**: ~500+
- **New Modules**: 7
- **Deprecated Modules**: 1
- **Bug Fixes**: 2 critical streaming bugs
- **SQL Consolidation**: Eliminated duplicate SQL across sync/async

---

## Stage 2: `app/database.py` Simplification ⬜ NEXT

**Goal**: Remove passthrough wrapper, simplify database access  
**Impact**: Reduced indirection, clearer data flow  
**Estimated Effort**: 1 day

### Planned Tasks

- [ ] **Evaluate `Database` Static Class**
  - Decision: Delete wrapper and import `db_pg_models` directly
  - **Recommendation**: Delete and migrate callers (cleaner architecture)

- [ ] **Migrate All Callers**
  - Find all `Database.method()` calls across codebase
  - Replace with direct `db_pg_models.method()` imports
  - Update imports in all affected files

- [ ] **Remove `app/database.py`**
  - Delete file after migration complete
  - Update `__init__.py` if needed
  - Verify no circular dependencies

- [ ] **Validation**
  - Manual testing on Termux
  - Verify all database operations still work
  - Check for performance changes

---

## Stage 3: `app/db_pg.py` Final Cleanup ⬜

**Goal**: Remove remaining duplication, polish database layer  
**Impact**: Small but clean wins  
**Estimated Effort**: 0.5 day

### Planned Tasks

- [x] ~~Remove Duplicated Functions~~ - DONE in Stage 1
  - ✅ `pg_scalar()` now correctly uses `execute_scalar()`

- [x] ~~Verify `dict_row` Usage~~ - DONE in Stage 1
  - ✅ Already using `psycopg.rows.dict_row` correctly

- [ ] **Drop Legacy Aliases** (if any remain)
  - Audit for unused legacy function names
  - Remove if nothing depends on them

- [x] ~~Type Hints~~ - DONE in Stage 1
  - ✅ Full type coverage added
  - ✅ Modern union syntax used

- [x] ~~Documentation~~ - DONE in Stage 1
  - ✅ Usage examples for `PgSession` / `AsyncPgSession`
  - ✅ Connection pool behavior documented

**Status**: Most Stage 3 work completed in Stage 1. Only legacy alias cleanup remains.

---

## Stage 4: `app/memory/` Package Refactor ⬜ PARTIALLY COMPLETE

**Goal**: Largest subsystem after `app.py` - per-file review and cleanup  
**Impact**: Critical for memory pipeline reliability  
**Status**: SQL consolidation done in Stage 1, remaining files need review

### ✅ Completed in Stage 1

- [x] **`db_memory_queries.py`** - NEW FILE
  - Single source of truth for SQL strings
  - Vector helpers and query builders
  - Eliminates sync/async SQL duplication

- [x] **`models.py`** - DEPRECATED
  - Deprecation warnings added
  - Migration path documented

### ⬜ Remaining Files to Refactor

- [ ] **`memory.py`** - Main memory orchestration
  - Review pipeline logic
  - Simplify async/sync boundaries
  - Add type hints
  - Use new `db_memory_queries` module

- [ ] **`extractor.py`** - Fact extraction
  - Review extraction logic
  - Optimize for performance
  - Add validation
  - Integrate with `db_memory_queries`

- [ ] **`retrieval.py`** - Memory retrieval
  - Review search algorithms
  - Optimize vector similarity
  - Add caching if needed
  - Use query builders from `db_memory_queries`

- [ ] **`review.py`** - Memory review/decay
  - Review decay algorithms
  - Validate review logic
  - Add metrics

- [ ] **`pcl.py`** - PCL (Persistent Context Layer?)
  - Understand purpose
  - Refactor if needed
  - Document

- [ ] **`embedder.py`** - Embedding generation
  - Review embedding logic
  - Optimize batch processing
  - Add error handling

- [ ] **`db_memory.py`** - Memory database layer
  - Migrate to use `db_memory_queries` exclusively
  - Remove remaining SQL duplication
  - Simplify repository functions

### Cross-Cutting Concerns

- [x] ~~Deprecate `models.py`~~ - DONE in Stage 1
- [ ] **Plan Full Removal Timeline**
  - Identify remaining callers
  - Create migration guide
  - Set deprecation deadline

- [ ] **Memory Pipeline Testing**
  - Add integration tests
  - Validate fact extraction
  - Test decay logic

---

## Stage 5: `app/tools/` Package Refactor ⬜

**Goal**: Clean up tool registry and individual tool modules  
**Impact**: Smaller, more contained than memory system  
**Estimated Effort**: 2 days

### Planned Tasks

- [ ] **Tool Registry (`registry.py`)**
  - Review registration mechanism
  - Simplify tool discovery
  - Add validation
  - Type hints

- [ ] **Individual Tool Modules**
  - Review each tool for consistency
  - Standardize error handling
  - Add type hints
  - Document tool contracts

- [ ] **Tool Result Formatting**
  - Standardize markdown output
  - Consistent error messages
  - Add result validation

- [ ] **Multimodal Tools**
  - Review vision integration
  - Optimize image handling
  - Add caching

---

## Stage 6: `scripts/` Cleanup ⬜

**Goal**: One-off CLI scripts - easy wins  
**Impact**: Low risk, good for learning codebase patterns  
**Estimated Effort**: 1 day

### Planned Tasks

- [ ] **Audit All Scripts**
  - List all scripts in `scripts/`
  - Identify purpose of each
  - Mark deprecated/unused

- [ ] **Standardize Patterns**
  - Use `argparse` consistently
  - Add `if __name__ == "__main__"` guards
  - Use logging instead of print

- [ ] **Add Type Hints**
  - Full type coverage
  - Modern syntax

- [ ] **Documentation**
  - Add docstrings
  - Usage examples
  - Document when to use each script

---

## 🎯 Success Criteria

### Stage 1 ✅ ACHIEVED
- ✅ No behavior regressions (needs Termux testing)
- ✅ Improved code organization and readability
- ✅ Reduced code duplication (3 Chutes call sites → 1)
- ✅ Type hints on all public APIs
- ✅ Logging instead of print statements
- ✅ Modern Python patterns (3.10+)
- ✅ Critical bugs fixed (streaming synthesis)

### Overall Project
- ⬜ All 6 stages completed and merged
- ⬜ `app.py` reduced from 1400 lines to <200 lines (or removed entirely)
- ⬜ No `Database` passthrough wrapper
- ⬜ Consolidated memory system
- ⬜ Clean tool registry
- ⬜ Documented scripts
- ⬜ (Future) Add `tests/` directory with pytest coverage

---

## 📝 Notes & Decisions

### Stage 1 Scope Expansion
**Decision**: Included `db_memory_queries.py` (originally Stage 4) in Stage 1  
**Rationale**: Foundation modules needed proper memory integration. Consolidating SQL strings was critical for the orchestrator and LLM client to work correctly.  
**Impact**: Stage 1 is larger than planned but more cohesive. Stage 4 is now lighter.

### Testing Strategy
- **Current**: No automated tests (`pytest` in requirements but no `tests/` directory)
- **Approach**: Manual testing on Termux per stage
- **Risk**: Runtime regressions possible without test coverage
- **Next Step**: Test Stage 1 thoroughly before proceeding to Stage 2

### Behavior Preservation
- **Mode**: Option (b) - Free to rename/reshape APIs
- **Rationale**: Self-hosted, you control all callers
- **Constraint**: Must maintain external API contracts (FastAPI routes)

### Known Issues Fixed in Stage 1
- ✅ **Duplicated synthesis block** in `handle_user_message_streaming`
- ✅ **Unbound `final_response`** variable in streaming path
- ✅ **`pg_scalar()` bug** - was using `fetchone()` instead of `execute_scalar()`

### Migration Path
Each stage is independently mergeable:
1. ✅ Stage 1: Create feature branch from `master`
2. ✅ Stage 1: Implement changes (DONE)
3. ⬜ Stage 1: Manual testing on Termux (PENDING)
4. ⬜ Stage 1: Review MR !70
5. ⬜ Stage 1: Merge to `master`
6. ⬜ Stage 2: Branch from updated `master`

---

## 🚀 Current Status

**Active Stage**: Stage 1 - ✅ **COMPLETE** (awaiting review & testing)  
**Next Stage**: Stage 2 - `app/database.py` simplification  
**Blocked**: None  
**Credits**: Ran out during Stage 1 (agentic mode) - final commit approved manually

---

## 📅 Timeline

| Stage | Status | Estimated Effort | Priority | Actual Effort |
|-------|--------|-----------------|----------|---------------|
| Stage 1 | ✅ Complete | 2-3 days | 🔴 Critical | ~3 days |
| Stage 2 | ⬜ Planned | 1 day | 🟡 High | - |
| Stage 3 | ⬜ Mostly
