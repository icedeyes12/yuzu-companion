# psycopg2 → psycopg (async v3) Migration Roadmap

**Project:** yuzu-companion
**Status:** PLANNING
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
- [ ] `init_pg_tables()` → `async def init_pg_tables()`
- [ ] `with PgSession() as s: s.execute(q)` → `async with AsyncPgSession() as s: await s.execute(q)`

### 2.2 — Profile operations
- [ ] `get_profile()` → `async def get_profile()`
- [ ] `update_profile()` → `async def update_profile()`
- [ ] `get_context()` → `async def get_context()`
- [ ] `update_context()` → `async def update_context()`
- [ ] `get_memory()` → `async def get_memory()`
- [ ] `update_memory()` → `async def update_memory()`

### 2.3 — ChatSession operations
- [ ] `get_active_session()` → `async def get_active_session()`
- [ ] `get_all_sessions()` → `async def get_all_sessions()`
- [ ] `create_session()` → `async def create_session()`
- [ ] `switch_session()` → `async def switch_session()`
- [ ] `rename_session()` → `async def rename_session()`
- [ ] `delete_session()` → `async def delete_session()`
- [ ] `update_session_memory()` → `async def update_session_memory()`
- [ ] `get_session_memory()` → `async def get_session_memory()`
- [ ] `increment_message_count()` → `async def increment_message_count()`

### 2.4 — APIKey operations
- [ ] `get_api_keys()` → `async def get_api_keys()`
- [ ] `get_api_key()` → `async def get_api_key()`
- [ ] `add_api_key()` → `async def add_api_key()`
- [ ] `remove_api_key()` → `async def remove_api_key()`

### 2.5 — Message operations
- [ ] `add_message()` → `async def add_message()`
- [ ] `get_session_messages()` → `async def get_session_messages()`
- [ ] `get_recent_messages()` → `async def get_recent_messages()`
- [ ] `get_chat_history()` → `async def get_chat_history()`
- [ ] `clear_session_messages()` → `async def clear_session_messages()`
- [ ] `get_message_count()` → `async def get_message_count()`
- [ ] `add_session_event()` → `async def add_session_event()`
- [ ] `get_recent_sessions()` → `async def get_recent_sessions()`
- [ ] `get_recent_sessions_for_session()` → `async def get_recent_sessions_for_session()`
- [ ] `get_session_conversation_summary()` → `async def get_session_conversation_summary()`
- [ ] `add_image_tools_message()` → `async def add_image_tools_message()`
- [ ] `add_tool_result()` → `async def add_tool_result()`
- [ ] `add_system_note()` → `async def add_system_note()`
- [ ] `get_chat_history_for_ai()` → `async def get_chat_history_for_ai()`
- [ ] `get_encryption_status()` → `async def get_encryption_status()`
- [ ] `get_all_encrypted_messages()` → `async def get_all_encrypted_messages()`
- [ ] `batch_decrypt_messages()` → `async def batch_decrypt_messages()`

### 2.6 — Update `app/database.py`
- [ ] Import all `async` versions from `db_pg_models`
- [ ] Update all `Database` static methods to `async def`
- [ ] Update `init_db()` → `async def init_db()`
- [ ] Update `get_db()` FastAPI dependency to `async def get_db()` + `yield`

---

## Phase 3 — Memory Layer: `app/memory/db_memory.py`

**Why third:** Depends on Phase 1 (pool) + Phase 2 (models).

### 3.1 — Imports
- [ ] Remove `from psycopg2.extras import Json`
- [ ] Add `from pgvector.psycopg import register_vector`
- [ ] Change `from app.db_pg import PgSession, pg_fetchone, pg_fetchall, pg_execute, vector_sql`
  → `from app.db_pg import AsyncPgSession, pg_fetchone, pg_fetchall, pg_execute`

### 3.2 — Vector handling
- [ ] Remove custom `vector_sql()` — psycopg v3 handles `list[float]` natively
- [ ] Remove `from psycopg2.extensions import register_adapter, AsIs`

### 3.3 — Convert all functions to async
- [ ] `save_fact()` → `async def save_fact()`
- [ ] `upsert_fact()` → `async def upsert_fact()`
- [ ] `search_similar()` → `async def search_similar()`
- [ ] `get_fact_by_id()` → `async def get_fact_by_id()`
- [ ] `get_facts_by_session()` → `async def get_facts_by_session()`
- [ ] `count_facts()` → `async def count_facts()`
- [ ] `update_last_accessed()` → `async def update_last_accessed()`
- [ ] `update_fact_importance()` → `async def update_fact_importance()`
- [ ] `increment_importance()` → `async def increment_importance()`
- [ ] `delete_fact()` → `async def delete_fact()`
- [ ] `delete_facts_by_session()` → `async def delete_facts_by_session()`
- [ ] `decay_facts()` → `async def decay_facts()`
- [ ] `get_memory_stats()` → `async def get_memory_stats()`

### 3.4 — `app/memory/embedder.py` (HTTP sync, not DB)
- [ ] `get_api_key("chutes")` is called from `db_pg_models` — after Phase 2, this becomes `await`
- [ ] Update `_get_session()` to call `await get_api_key()` (needs async wrapper)
- [ ] `embed_texts()` stays sync (HTTP external API) — add `async def embed_texts()` wrapper that calls sync version in thread pool

### 3.5 — `app/memory/retrieval.py`
- [ ] `get_session_messages()` from `db_pg_models` → `await`
- [ ] All `db_memory` function calls → `await`
- [ ] `_embed_query()` calls `embed_text()` → wrap in `asyncio.get_event_loop().run_in_executor()` or refactor `embed_text` to async
- [ ] `retrieve_static_memories()` → `async def retrieve_static_memories()`
- [ ] `retrieve_dynamic_memories()` → `async def retrieve_dynamic_memories()`
- [ ] `retrieve_memory()` → `async def retrieve_memory()`
- [ ] `format_memory()` stays sync (pure formatting, no DB)

### 3.6 — `app/memory/extractor.py`
- [ ] `upsert_semantic_memory()` calls `embed_text()` + `db_memory` functions → all `await`
- [ ] `create_episodic_memory()` calls `embed_text()` + `db_memory` functions → all `await`
- [ ] `process_messages_for_memory()` → `async def process_messages_for_memory()`

### 3.7 — `app/memory/review.py`
- [ ] `run_decay()` → `async def run_decay()` (calls `decay_facts()` which is now async)

### 3.8 — `app/memory/segmenter.py`
- [ ] `get_session_messages()` → `await`
- [ ] `get_facts_by_session()` → `await`
- [ ] `save_fact()` → `await`
- [ ] `segment_session()` → `async def segment_session()`

---

## Phase 4 — Tool Layer

**Why fourth:** Tools are sync callers that will need refactoring to async.

### 4.1 — `app/tools/memory_store.py`
- [ ] `execute()` → `async def execute()` (since it calls `await`-ed `save_fact`, `search_similar`, `increment_importance`, `embed_texts`, `get_profile`)
- [ ] `_classify_category_llm()` → `async def _classify_category_llm()` (calls async AI manager)

### 4.2 — `app/tools/memory_search.py`
- [ ] `execute()` → `async def execute()` (calls `await`-ed `retrieve_memory`, `format_memory`)
- [ ] `Database.get_profile()` → `await Database.get_profile()`

### 4.3 — `app/tools/registry.py`
- [ ] `execute_tool()` → `async def execute_tool()`
- [ ] `get_tool_definitions()`, `get_tool_definition()`, `get_tools_by_role()`, `get_tool_role()` — stay sync (only schema lookups)
- [ ] `_get_partner_name()` → `async def _get_partner_name()` (calls `await Database.get_profile()`)
- [ ] Update all callers of `execute_tool()` in `app/app.py` and `web.py`

---

## Phase 5 — App Layer: `app/app.py` + `web.py`

**Why last:** These are the top-level callers. All dependencies must be async first.

### 5.1 — `app/app.py`
- [ ] All `Database.X()` calls → `await Database.X()` (all DB operations are now async)
- [ ] All `execute_tool()` calls → `await execute_tool()`
- [ ] All `start_session()`, `end_session_cleanup()`, `summarize_memory()` → `async def`
- [ ] `handle_user_message()` → `async def handle_user_message()`
- [ ] `handle_user_message_streaming()` → `async def handle_user_message_streaming()`
- [ ] `get_ai_manager()`, `reload_ai_manager()` — stay sync (in-memory singletons)
- [ ] AI provider HTTP calls (requests library) — optionally async with `httpx`, but optional for now

### 5.2 — `web.py` (FastAPI already async-native)
- [ ] All `Database.X()` calls → `await Database.X()`
- [ ] All `execute_tool()` calls → `await execute_tool()`
- [ ] `start_session()` → `await start_session()`
- [ ] `end_session_cleanup()` → `await end_session_cleanup()`

---

## Phase 6 — Cleanup & Deprecation Removal

- [ ] Remove sync stubs from `app/db_pg.py` (`PgSession`, `pg_fetchone`, etc.)
- [ ] Remove backward-compat aliases in `app/database.py`
- [ ] Update `requirements.txt`: remove `psycopg2-binary`, add `psycopg>=3.1`, `psycopg_pool`, `pgvector`
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
