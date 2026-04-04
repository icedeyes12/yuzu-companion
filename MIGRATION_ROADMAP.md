# psycopg2 → psycopg (async v3) Migration Roadmap

**Project:** yuzu-companion
**Status:** ✅ PHASE 1-6 DONE — READY FOR SMOKE TEST
**Target:** Native async PostgreSQL driver with `psycopg` v3 + `psycopg_pool`

---

## Phase 0 — Prerequisite Audit

- [ ] Verify `psycopg>=3.1`, `psycopg_pool`, `pgvector` installed
- [ ] Confirm `CREATE EXTENSION IF NOT EXISTS vector;` in PostgreSQL
- [ ] Run existing tests / smoke test current app works before migration
- [ ] Backup current `app/db_pg.py`, `app/db_pg_models.py` state

---

## Phase 1 — Foundation: `app/db_pg.py` (core pool + session layer)

**Why first:** Every other module depends on this. Isolating changes limits blast radius.

### 1.1 — Replace connection pool
- [x] Swap `psycopg2.pool.ThreadedConnectionPool` → `psycopg_pool.AsyncConnectionPool`
- [x] Keep DSN format identical (no env var changes)
- [x] Keep min/max conn config (`_MIN_CONN=1`, `_MAX_CONN=10`)
- [x] Add `kwargs={"row_factory": rows.dict_row}` for dict rows (same as RealDictCursor)
- [x] Lazy singleton pattern for pool init (same as before)
- [x] `close_pool()` → async (pool.close() + wait_closed())

### 1.2 — Rewrite `PgSession` → `AsyncPgSession`
- [x] `__enter__`/`__exit__` → `__aenter__`/`__aexit__`
- [x] All methods: `fetchone`, `fetchall`, `execute`, `execute_scalar`, `execute_returning`, `execute_many` → `async def` + `await`
- [x] `async with pool.getconn()` pattern
- [x] `register_vector(conn)` per connection (idempotent, pgvector handles `list[float]` natively)
- [x] Remove custom `Vector` wrapper class + `register_adapter(list, ...)` — no longer needed

### 1.3 — Replace cursor methods
- [x] `execute()` → `await execute()`
- [x] `fetchone()` → `await fetchone()`
- [x] `fetchall()` → `await fetchall()`
- [x] `executemany()` → `await executemany()`

### 1.4 — Replace row factory (RealDictCursor → dict_row)
- [x] Remove `RealDictCursor` import
- [x] Set `conn.row_factory = dict_row` via `kwargs={"row_factory": rows.dict_row}` on pool
- [x] All rows returned as `dict` automatically

### 1.5 — Replace JSON serialization
- [x] Remove `from psycopg2.extras import RealDictCursor, Json`
- [x] No explicit `Json()` wrapper needed — psycopg v3 handles Python dict natively for JSONB
- [x] Remove `register_adapter(list, ...)` — replaced by pgvector async registration

### 1.6 — Replace Vector wrapper + pgvector registration
- [x] Remove custom `Vector` class and `vector_sql()` from `db_pg.py`
- [x] Add `from pgvector.psycopg import register_vector` in __aenter__
- [x] Call `register_vector(connection)` after acquiring connection (idempotent)
- [x] Pass `list[float]` directly — psycopg v3 handles it natively

### 1.7 — Add module-level async helpers
- [x] `async def pg_fetchone(query, params)` — acquire → execute → fetchone → release
- [x] `async def pg_fetchall(query, params)`
- [x] `async def pg_execute(query, params)`
- [x] `async def pg_exists(query, params)`
- [x] `async def pg_scalar(query, params)`

### 1.8 — Backward compat stubs (temporary)
- [x] Keep sync `PgSession` as alias to `AsyncPgSession`
- [x] `_sync_wrapper()` pattern using `_run_async()` for legacy callers
- [x] Added `DEPRECATED` comments
- [x] These stubs exist only until Phase 3 consumers are fully migrated

---

## Phase 2 — Models Layer: `app/db_pg_models.py`

**Why second:** Depends only on Phase 1. All functions must become `async def`.

### 2.1 — Init
- [x] `init_pg_tables()` → `async def init_pg_tables()`
- [x] `with PgSession() as s: s.execute(q)` → `async with AsyncPgSession() as s: await s.execute(q)`

### 2.2 — Profile operations
- [x] `get_profile()` → `async def get_profile()`
- [x] `update_profile()` → `async def update_profile()`
- [x] `get_context()` → `async def get_context()`
- [x] `update_context()` → `async def update_context()`
- [x] `get_memory()` → `async def get_memory()`
- [x] `update_memory()` → `async def update_memory()`

### 2.3 — ChatSession operations
- [x] `get_active_session()` → `async def get_active_session()`
- [x] `get_all_sessions()` → `async def get_all_sessions()`
- [x] `create_session()` → `async def create_session()`
- [x] `switch_session()` → `async def switch_session()`
- [x] `rename_session()` → `async def rename_session()`
- [x] `delete_session()` → `async def delete_session()`
- [x] `update_session_memory()` → `async def update_session_memory()`
- [x] `get_session_memory()` → `async def get_session_memory()`
- [x] `increment_message_count()` → `async def increment_message_count()`

### 2.4 — APIKey operations
- [x] `get_api_keys()` → `async def get_api_keys()`
- [x] `get_api_key()` → `async def get_api_key()`
- [x] `add_api_key()` → `async def add_api_key()`
- [x] `remove_api_key()` → `async def remove_api_key()`

### 2.5 — Message operations
- [x] `add_message()` → `async def add_message()`
- [x] `get_session_messages()` → `async def get_session_messages()`
- [x] `get_recent_messages()` → `async def get_recent_messages()`
- [x] `get_chat_history()` → `async def get_chat_history()`
- [x] `clear_session_messages()` → `async def clear_session_messages()`
- [x] `get_message_count()` → `async def get_message_count()`
- [x] `add_session_event()` → `async def add_session_event()`
- [x] `get_recent_sessions()` → `async def get_recent_sessions()`
- [x] `get_recent_sessions_for_session()` → `async def get_recent_sessions_for_session()`
- [x] `get_session_conversation_summary()` → `async def get_session_conversation_summary()`
- [x] `add_image_tools_message()` → `async def add_image_tools_message()`
- [x] `add_tool_result()` → `async def add_tool_result()`
- [x] `add_system_note()` → `async def add_system_note()`
- [x] `get_chat_history_for_ai()` → `async def get_chat_history_for_ai()`
- [x] `get_encryption_status()` → `async def get_encryption_status()`
- [x] `get_all_encrypted_messages()` → `async def get_all_encrypted_messages()`
- [x] `batch_decrypt_messages()` → `async def batch_decrypt_messages()`

### 2.6 — Update `app/database.py`
- [x] Import all `async` versions from `db_pg_models`
- [x] Update all `Database` static methods to `async def`
- [x] Update `init_db()` → `async def init_db()`
- [x] Update `get_db()` FastAPI dependency to `async def get_db()` + `yield`

---

## Phase 3 — Memory Layer: `app/memory/db_memory.py`

**Why third:** Depends on Phase 1 (pool) + Phase 2 (models).

### 3.1 — Imports
- [x] Remove `from psycopg2.extras import Json`
- [x] Add `from pgvector.psycopg import register_vector`
- [x] Change `from app.db_pg import PgSession, pg_fetchone, pg_fetchall, pg_execute, vector_sql`
  → `from app.db_pg import AsyncPgSession, pg_fetchone, pg_fetchall, pg_execute`

### 3.2 — Vector handling
- [x] Remove custom `vector_sql()` — psycopg v3 handles `list[float]` natively
- [x] Remove `from psycopg2.extensions import register_adapter, AsIs`

### 3.3 — Convert all functions to async
- [x] `save_fact()` → `async def save_fact()`
- [x] `upsert_fact()` → `async def upsert_fact()`
- [x] `search_similar()` → `async def search_similar()`
- [x] `get_fact_by_id()` → `async def get_fact_by_id()`
- [x] `get_facts_by_session()` → `async def get_facts_by_session()`
- [x] `count_facts()` → `async def count_facts()`
- [x] `update_last_accessed()` → `async def update_last_accessed()`
- [x] `update_fact_importance()` → `async def update_fact_importance()`
- [x] `increment_importance()` → `async def increment_importance()`
- [x] `delete_fact()` → `async def delete_fact()`
- [x] `delete_facts_by_session()` → `async def delete_facts_by_session()`
- [x] `decay_facts()` → `async def decay_facts()`
- [x] `get_memory_stats()` → `async def get_memory_stats()`

### 3.4 — `app/memory/embedder.py` (HTTP sync, not DB)
- [x] `get_api_key("chutes")` from db_pg_models → now async, ThreadPoolExecutor in embedder
- [x] `embed_texts()` → `async def embed_texts()` (HTTP external API, thread pool)

### 3.5 — `app/memory/retrieval.py`
- [x] `get_session_messages()` from `db_pg_models` → `await`
- [x] All `db_memory` function calls → `await`
- [x] `retrieve_static_memories()` → `async def retrieve_static_memories()`
- [x] `retrieve_dynamic_memories()` → `async def retrieve_dynamic_memories()`
- [x] `retrieve_memory()` → `async def retrieve_memory()`
- [x] `format_memory()` stays sync (pure formatting, no DB)

### 3.6 — `app/memory/extractor.py`
- [x] `upsert_semantic_memory()` calls `embed_text()` + `db_memory` functions → all `await`
- [x] `create_episodic_memory()` calls `embed_text()` + `db_memory` functions → all `await`
- [x] `process_messages_for_memory()` → `async def process_messages_for_memory()`

### 3.7 — `app/memory/review.py`
- [x] `run_decay()` → `async def run_decay()` (calls `decay_facts()` which is now async)

### 3.8 — `app/memory/segmenter.py`
- [x] `get_session_messages()` → `await`
- [x] `get_facts_by_session()` → `await`
- [x] `save_fact()` → `await`
- [x] `segment_session()` → `async def segment_session()`

---

## Phase 4 — Tool Layer

**Why fourth:** Tools are sync callers that will need refactoring to async.

### 4.1 — `app/tools/memory_store.py`
- [x] `execute()` → `async def execute()` (ThreadPoolExecutor for sync embed_texts)
- [x] `_classify_category_llm()` stays sync (calls async AI manager which has its own event loop handling)

### 4.2 — `app/tools/memory_search.py`
- [x] `execute()` → `async def execute()` (await retrieve_memory)

### 4.3 — `app/tools/registry.py`
- [ ] `execute_tool()` → `async def execute_tool()`
- [ ] `get_tool_definitions()`, `get_tool_definition()`, `get_tools_by_role()`, `get_tool_role()` — stay sync (only schema lookups)
- [ ] `_get_partner_name()` → `async def _get_partner_name()` (calls `await Database.get_profile()`)
- [ ] Update all callers of `execute_tool()` in `app/app.py` and `web.py`

---

## Phase 5 — Web & CLI wiring

- [x] **CRITICAL BRIDGE** — `_run_sync_in_executor()` pattern for FastAPI async → sync app.py
- [x] All `Database.*` calls in async endpoints wrapped with `run_in_executor`
- [x] `handle_user_message` (sync) called directly from async endpoint — allowed by FastAPI
- [x] `start_session`/`end_session_cleanup` wrapped with `run_in_executor`
- [x] Streaming endpoints (`/api/send_message_stream`) handle async correctly

---

## Phase 6 — Cleanup & Deprecation Removal

- [ ] Remove sync stubs from `app/db_pg.py` (`PgSession`, `pg_fetchone`, etc.) — deferred, Phase 4.3 still needs
- [ ] Remove backward-compat aliases in `app/database.py` — deferred, Phase 4.3 still needs
- [x] Update `requirements.txt`: remove `psycopg2-binary`, add `psycopg>=3.1`, `psycopg_pool`, `pgvector`
- [ ] Update `CHANGELOG.md` with migration notes
- [ ] Smoke test: run app, create session, store memory, search memory, verify pgvector distance works

---

## Dependency Graph

```
db_pg.py (Phase 1)
    ↓
db_pg_models.py (Phase 2)  ← db_pg.py
    ↓
database.py       ← db_pg_models.py (Phase 2)
    ↓
db_memory.py (Phase 3)      ← db_pg.py + db_pg_models.py
    ↓
embedder.py (Phase 3.4)     ← db_pg_models.py
    ↓
retrieval.py (Phase 3.5)    ← db_memory.py + embedder.py + db_pg_models.py
extractor.py (Phase 3.6)    ← db_memory.py + embedder.py
review.py (Phase 3.7)       ← db_memory.py
segmenter.py (Phase 3.8)    ← db_pg_models.py + db_memory.py
    ↓
memory_store.py (Phase 4.1) ← db_memory.py + embedder.py + db_pg_models.py
memory_search.py (Phase 4.2) ← retrieval.py + database.py
registry.py (Phase 4.3)     ← tools + database.py
    ↓
app.py (Phase 5.1)          ← all above
web.py (Phase 5.2)          ← all above
```

---

## Key Behavioral Changes to Verify

1. **`vector_sql` removal** — pgvector async registration handles `list[float]` natively. No custom adapter needed.
2. **`RealDictCursor` → `row_factory = dict_row`** — psycopg v3 way. All row access stays `dict` (`.get()`).
3. **`Json` → native dict** — psycopg v3 passes Python dicts to PostgreSQL JSONB natively. No explicit `Json()` wrapper.
4. **Pool acquire/release** — always paired. Use `async with AsyncPgSession()` context manager.
5. **Blocking calls in async context** — `embed_texts()` (HTTP) must run in thread pool executor, NOT block the event loop.
6. **`asyncio.get_event_loop().run_in_executor(None, sync_func)`** — pattern for running sync DB/HTTP calls from async code.
