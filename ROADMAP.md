# Refactor Roadmap: Complete Codebase Pythonic Refactor

**Project**: yuzu-companion  
**Branch**: `refactor/stage-1-app-decomposition` → `refactor/stage-4-memory-package`  
**MR**: [!70](https://gitlab.com/icedeyes12-group/yuzu-companion/-/merge_requests/70)  
**Status**: Stage 4 In Progress 🔄 | Stages 1-3 Complete ✅  
**Strategy**: Staged approach - one MR per concern, independently testable  
**Behavior Preservation**: Option (b) - rename/reshape APIs freely (self-hosted, controlled callers)

---

## 📋 Overview

Refactor ~30 Python files in `app/` package, with `app.py` (1400 lines) being the primary monolith. Breaking into 6 coordinated stages to avoid thousands-of-lines MRs that can't be reviewed or tested on Termux.

---

## Stage 1: Foundation Modules ✅ COMPLETE & MERGED

**Goal**: Split 1400-line monolith into focused modules  
**Impact**: Highest leverage, biggest maintainability win  
**Files Changed**: 23 files  
**Status**: ✅ Merged to master

### Completed Work

- ✅ **`app/logging_config.py`** - Centralized logging
- ✅ **`app/commands.py`** - Command detection & execution with `StreamFilter`
- ✅ **`app/prompts.py`** - System prompt assembly
- ✅ **`app/llm_client.py`** - AI response generation + `chutes_chat()` helper
- ✅ **`app/orchestrator.py`** - Message handling entrypoint
- ✅ **`app/profile_analysis.py`** - Profile & memory analysis
- ✅ **`app/db_pg.py`** - Enhanced PostgreSQL layer
- ✅ **`app/memory/db_memory_queries.py`** - SQL consolidation (partial Stage 4 work)
- ✅ **Bug Fixes**: Streaming synthesis, unbound variables, `pg_scalar()` fix

**Outcome**: 
- 3 Chutes call sites → 1 consolidated helper
- All `print()` → `logging`
- Full type hints with PEP 604 syntax
- 2 critical streaming bugs fixed

---

## Stage 2: `app/database.py` Simplification ✅ COMPLETE & MERGED

**Goal**: Remove passthrough wrapper, simplify database access  
**Impact**: Reduced indirection, clearer data flow  
**Status**: ✅ Merged to master

### Completed Work

- ✅ **Removed `Database` Static Class**
  - Deleted passthrough wrapper
  - Migrated all callers to direct `db_pg_models` imports

- ✅ **Migrated All Callers**
  - Updated imports across entire codebase
  - Verified no circular dependencies

- ✅ **Deleted `app/database.py`**
  - File removed after migration complete
  - Updated `__init__.py`

- ✅ **Validation**
  - Manual testing on Termux
  - All database operations verified working
  - No performance regressions

**Outcome**: Cleaner architecture, direct database access, reduced indirection

---

## Stage 3: `app/db_pg.py` Final Cleanup ✅ COMPLETE & MERGED

**Goal**: Remove remaining duplication, polish database layer  
**Impact**: Small but clean wins  
**Status**: ✅ Merged to master

### Completed Work

- ✅ **Removed Duplicated Functions**
  - `pg_scalar()` now correctly uses `execute_scalar()`
  - Eliminated redundant helper functions

- ✅ **Verified `dict_row` Usage**
  - Confirmed `psycopg.rows.dict_row` used correctly throughout

- ✅ **Dropped Legacy Aliases**
  - Removed unused legacy function names
  - Cleaned up backward compatibility stubs

- ✅ **Type Hints**
  - Full type coverage on all functions
  - Modern union syntax (`X | None`)

- ✅ **Documentation**
  - Usage examples for `PgSession` / `AsyncPgSession`
  - Connection pool behavior documented
  - All public APIs have docstrings

**Outcome**: Database layer fully modernized and documented

---

## Stage 4: `app/memory/` Package Refactor 🔄 IN PROGRESS

**Goal**: Largest subsystem - per-file review, SQL consolidation, sync/async unification  
**Impact**: Critical for memory pipeline reliability  
**Status**: 🔄 In Progress - 3-commit plan

### 📊 Memory System Health Check (Pre-Refactor)

**Database Status** (verified before refactor):
- ✅ Extensions: `pg_trgm 1.6`, `vector 0.8.2`, `plpgsql 1.0`
- ✅ Total facts: 2,641
- ✅ Active facts: 1,586
- ✅ Pipeline working (not just fallback to recent history)
- ⚠️ **Known Issue**: `pending_review` drift (512 in column vs 230 in JSON)
  - Harmless to retrieval but real drift
  - Will fix in Stage 4.5 with sign-off

### 🎯 7-Step Plan (3 Commits)

#### Stage 4.1: Extract Memory SQL Constants + Delete Dead Code ✅ COMPLETE

**Commit 1 of 3** — ✅ Completed 2026-04-19

- [x] **Extract SQL Constants**
  - Move all SQL strings to `db_memory_queries.py`
  - Create query builder functions
  - Add vector literal helpers

- [x] **Delete Dead Code**
  - `models.py` already deleted (not present in directory)
  - Deleted `upsert_fact()` (unused)
  - Deleted `search_trgm_keywords()` (DEPRECATED)
  - Deleted `update_fact_importance()` (DEPRECATED)
  - Removed duplicate `_normalize()` - use `normalize_vector` from `db_memory_queries`

- [x] **Update Imports**
  - Updated `db_memory.py` to import from `db_memory_queries`
  - Updated `retrieval.py` to import from `db_memory_queries`
  - Fixed scripts to import `pg_fetchall`/`pg_execute` from `db_pg`

- [x] **Logging Migration (partial)**
  - Converted `print()` to `logging` in `db_memory.py`
  - Converted `print()` to `logging` in `retrieval.py`

- [x] **Bug Fixes**
  - Fixed syntax error in `tests/test_db_queries.py` (walrus operator)

#### Stage 4.2: Unify Sync/Async in `db_memory.py` and `retrieval.py` 🔄 IN PROGRESS

**Commit 2 of 3**

- [x] **`db_memory.py` Unification**
  - ✅ Consolidate sync/async repository functions - both use same SQL constants
  - ✅ Use `db_memory_queries` builders exclusively
  - ✅ Remove SQL duplication - done in Stage 4.1

- [ ] **`retrieval.py` Unification**
  - ✅ Use query builders from `db_memory_queries` - done in Stage 4.1
  - [ ] Optimize vector similarity search
  - [ ] Add caching if beneficial

- [ ] **Testing**
  - Verify retrieval still works
  - Test vector search accuracy
  - Validate sync/async parity

#### Stage 4.3: Replace `print()` with `logging` + Add Tests ⬜

**Commit 3 of 3**

- [ ] **Logging Migration (remaining files)**
  - Replace all `print()` calls in `memory_review.py`
  - Replace all `print()` calls in `memory.py`
  - Replace all `print()` calls in `extractor.py`
  - Replace all `print()` calls in `pcl.py`
  - Replace all `print()` calls in `review.py`

- [ ] **Add Tests**
  - Unit tests for query builders
  - Integration tests for retrieval
  - Vector search validation tests
  - Fact extraction tests

- [ ] **Documentation**
  - Update docstrings
  - Add usage examples
  - Document memory pipeline flow

### ⬜ Remaining Files (After 3-Commit Plan)

- [ ] **`memory.py`** - Main memory orchestration
  - Review pipeline logic
  - Simplify async/sync boundaries
  - Add type hints

- [ ] **`extractor.py`** - Fact extraction
  - Review extraction logic
  - Optimize for performance
  - Add validation

- [ ] **`review.py`** - Memory review/decay
  - Review decay algorithms
  - Validate review logic
  - Add metrics

- [ ] **`pcl.py`** - PCL (Persistent Context Layer)
  - Understand purpose
  - Refactor if needed
  - Document

- [ ] **`embedder.py`** - Embedding generation
  - Review embedding logic
  - Optimize batch processing
  - Add error handling

### 🔧 Stage 4.5: Fix `pending_review` Drift (Planned)

**Deferred until after 3-commit plan**

- [ ] **Investigate Drift**
  - 512 in column vs 230 in JSON
  - Identify why `TRUE` values don't reset

- [ ] **Implement Fix**
  - Add proper reset logic
  - Sync column with JSON state
  - Add validation

- [ ] **Testing**
  - Verify drift eliminated
  - Monitor over time
  - Add regression test

**Note**: Awaiting sign-off before implementing fix

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

### Per-Stage Completion
- ✅ Stage 1: No behavior regressions, improved organization, bugs fixed
- ✅ Stage 2: Database wrapper removed, cleaner architecture
- ✅ Stage 3: Database layer polished and documented
- 🔄 Stage 4: Memory system consolidated, sync/async unified, tests added
- ⬜ Stage 5: Tool registry cleaned up
- ⬜ Stage 6: Scripts standardized

### Overall Project
- ⬜ All 6 stages completed and merged
- ⬜ `app.py` reduced from 1400 lines to <200 lines (or removed entirely)
- ✅ No `Database` passthrough wrapper (Stage 2 complete)
- 🔄 Consolidated memory system (Stage 4 in progress)
- ⬜ Clean tool registry
- ⬜ Documented scripts
- 🔄 Tests added (Stage 4.3 will add first tests)

---

## 📝 Notes & Decisions

### Stage 4 Breakdown Rationale
**Decision**: Split Stage 4 into 3 focused commits  
**Rationale**: Memory system is complex. Breaking into SQL extraction → sync/async unification → testing makes each commit reviewable and testable independently.  
**Impact**: Stage 4 takes longer but each step is safer.

### Pending Review Drift
**Issue**: 512 facts marked `pending_review=TRUE` in column vs 230 in JSON  
**Impact**: Harmless to retrieval (doesn't affect search results)  
**Fix**: Deferred to Stage 4.5 pending sign-off  
**Root Cause**: `TRUE` values accumulate but never get reset properly

### Testing Strategy
- **Current**: No automated tests (pytest in requirements but no `tests/` directory)
- **Stage 4.3**: Will add first tests for memory system
- **Future**: Expand test coverage in later stages
- **Approach**: Manual testing on Termux + automated tests where feasible

### Migration Path
- ✅ Stage 1: Merged to master
- ✅ Stage 2: Merged to master
- ✅ Stage 3: Merged to master
- 🔄 Stage 4: In progress (3 commits)
  - ⬜ Stage 4.1: SQL extraction + dead code removal
  - ⬜ Stage 4.2: Sync/async unification
  - ⬜ Stage 4.3: Logging + tests
  - ⬜ Stage 4.5: Fix pending_review drift (deferred)
- ⬜ Stage 5: Branch from updated master after Stage 4
- ⬜ Stage 6: Branch from updated master after Stage 5

---

## 🚀 Current Status

**Active Stage**: Stage 4.1 - Extract Memory SQL Constants + Delete Dead Code  
**Next Commit**: Stage 4.1 (1 of 3)  
**Blocked**: None  
**Credits**: Sufficient for Stage 4 work

---

## 📅 Timeline

| Stage | Status | Estimated | Priority | Actual | Notes |
|-------|--------|-----------|----------|--------|-------|
| Stage 1 | ✅ Complete | 2-3 days | 🔴 Critical | ~3 days | Merged |
| Stage 2 | ✅ Complete | 1 day | 🟡 High | ~1 day | Merged |
| Stage 3 | ✅ Complete | 0.5 day | 🟢 Medium | ~0.5 day | Merged |
| Stage 4.1 | ✅ Complete | 1 day | 🔴 Critical | ~1 day | SQL + dead code |
| Stage 4.2 | 🔄 In Progress | 1.5 days | 🔴 Critical | - | Sync/async unify |
| Stage 4.3 | ⬜ Planned | 1 day | 🔴 Critical | - | Logging + tests |
| Stage 4.5 | ⬜ Deferred | 0.5 day | 🟡 High | - | Pending review fix |
| Stage 5 | ⬜ Planned | 2 days | 🟡 High | - | Tools package |
| Stage 6 | ⬜ Planned | 1 day | 🟢 Low | - | Scripts cleanup |

**Total Progress**: 3/6 stages complete (50%) + Stage 4 in progress (0/3 commits)

---

## 🔍 Stage 4 Detailed Breakdown

### Stage 4.1: SQL Extraction + Dead Code Removal

**Files to Modify**:
- `app/memory/db_memory_queries.py` (expand)
- `app/memory/models.py` (delete)
- `app/memory/db_memory.py` (update imports)
- `app/memory/retrieval.py` (update imports)

**Expected Changes**:
- ~500 lines moved to `db_memory_queries.py`
- ~200 lines deleted (dead code)
- ~50 import updates

### Stage 4.2: Sync/Async Unification

**Files to Modify**:
- `app/memory/db_memory.py` (major refactor)
- `app/memory/retrieval.py` (major refactor)

**Expected Changes**:
- ~300 lines consolidated (remove duplication)
- Unified function signatures
- Consistent error handling

### Stage 4.3: Logging + Tests

**Files to Modify**:
- All `app/memory/*.py` files (logging)
- `tests/memory/` (new directory)

**Expected Changes**:
- ~50 `print()` → `logging` replacements
- ~500 lines of new tests
- Test fixtures and helpers

---

**Last Updated**: 2026-04-19  
**Author**: Bani Baskara (@icedeyes12)  
**Current Branch**: `refactor/stage-4-memory-package`