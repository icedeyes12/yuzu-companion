# Async Migration + plast-mem Re-adapt Roadmap

## Goal
Migrate dari psycopg2 (sync) ke psycopg v3 (async) + re-adapt dengan plast-mem patterns.

## Constraints
- **BM25 tidak tersedia di Termux** → tetap pakai pg_trgm + tsvector
- **No breaking changes** → maintain existing API surface
- **Phase by phase** → validate setiap phase dengan `ruff check` + `python3 -m py_compile`

---

## Phase 1: psycopg v3 Foundation (db_pg.py)

### Changes
- Replace `psycopg2` dengan `psycopg` (v3)
- Use `AsyncConnectionPool` instead of `ThreadedConnectionPool`
- Keep vector literal interpolation (pgvector doesn't support binary wire format)

### Files
- `requirements.txt` → psycopg[binary,pool] >= 3.1
- `app/db_pg.py` → async pool + async context manager

### Validation
```bash
ruff check app/db_pg.py
python3 -m py_compile app/db_pg.py
```

---

## Phase 2: Schema Migration (valid_at column)

### Changes
- Add `valid_at` column to `semantic_facts` for temporal validity
- plast-mem pattern: `valid_at` = when fact became true, `invalid_at` = when fact became false

### SQL
```sql
ALTER TABLE semantic_facts
ADD COLUMN IF NOT EXISTS valid_at TIMESTAMP DEFAULT NOW();
```

---

## Phase 3: Async DB Layer (db_pg_models.py, database.py)

### Changes
- Convert all sync functions to async
- Use `async with` for connection acquisition
- Update callers to await results

### Files
- `app/db_pg_models.py` → async functions
- `app/database.py` → async functions

---

## Phase 4: Async Memory Layer

### Changes
- Convert `app/memory/db_memory.py` to async
- Convert `app/memory/retrieval.py` to async
- Convert `app/memory/memory.py` to async

---

## Phase 5: Web Layer Bridge

### Changes
- `web.py` already has async routes
- Use `run_in_executor` for any remaining sync operations
- OR fully convert to async/await

---

## Phase 6: plast-mem Re-adapt

### Category Enforcement
Ensure PCL enforces 8-category taxonomy:
- Identity, Preference, Interest, Personality
- Relationship, Experience, Goal, Guideline

### Temporal Validity
- `valid_at` set on creation
- `invalid_at` set when contradicted

### FSRS Scope
- Semantic facts: temporal validity (no decay)
- Episodic facts: FSRS decay

---

## Progress

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | ✅ DONE | psycopg v3 foundation - db_pg.py async pool + sync wrappers |
| Phase 2 | ✅ DONE | Schema migration - valid_at column added to save_fact |
| Phase 3 | 🔲 TODO | Async DB layer |
| Phase 4 | 🔲 TODO | Async memory layer |
| Phase 5 | 🔲 TODO | Web layer bridge |
| Phase 6 | 🔲 TODO | plast-mem re-adapt |

---

## Run After Each Phase
```bash
ruff check app/
python3 -m py_compile app/
```
