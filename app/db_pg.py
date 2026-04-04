# FILE: app/db_pg.py
# DESCRIPTION: PostgreSQL connection pool and raw SQL helpers.
#             Uses psycopg (v3) native async driver + psycopg_pool.
#             All operations are async — must be called with await.
#
# MIGRATED: psycopg2 → psycopg async v3
# - ThreadedConnectionPool → AsyncConnectionPool
# - RealDictCursor → row_factory = dict_row
# - register_adapter(list) → pgvector.psycopg.register_vector

from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg import rows
from psycopg_pool import AsyncConnectionPool
from pgvector.psycopg import register_vector

# ── Env defaults (Termux/local dev) ──────────────────────────────────────────
_PG_HOST     = os.getenv("PGHOST", os.getenv("PG_HOST", "127.0.0.1"))
_PG_PORT     = os.getenv("PGPORT", os.getenv("PG_PORT", "5432"))
_PG_DBNAME   = os.getenv("PGDATABASE", os.getenv("PG_DBNAME", "yuzuki"))
_PG_USER     = os.getenv("PGUSER", os.getenv("PG_USER", "icedeyes12"))
_PG_PASSWORD = os.getenv("PGPASSWORD", os.getenv("PG_PASSWORD", ""))
_MIN_CONN    = 1
_MAX_CONN    = 10

# ── Global pool (lazy singleton) ──────────────────────────────────────────────
_pool: AsyncConnectionPool | None = None


def _build_dsn() -> str:
    return (
        f"host={_PG_HOST} port={_PG_PORT} dbname={_PG_DBNAME} "
        f"user={_PG_USER} password={_PG_PASSWORD}"
    )


def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            _build_dsn(),
            min_size=_MIN_CONN,
            max_size=_MAX_CONN,
            kwargs={"row_factory": rows.dict_row},
        )
        print(f"[db_pg] Async pool created: {_PG_HOST}:{_PG_PORT}/{_PG_DBNAME}")
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
        print("[db_pg] Pool closed")


# ── Async session context manager ─────────────────────────────────────────────
class AsyncPgSession:
    """
    Async context manager for one-off queries.
    Acquires a connection from the async pool, commits on success,
    rolls back on exception.

    Usage:
        async with AsyncPgSession() as s:
            row = await s.fetchone("SELECT * FROM profiles LIMIT 1")
            await s.execute("INSERT INTO ...")
    """
    __slots__ = ('conn', 'autocommit')

    def __init__(self, autocommit: bool = False):
        self.autocommit = autocommit
        self.conn: psycopg.AsyncConnection | None = None

    async def __aenter__(self) -> "AsyncPgSession":
        pool = get_pool()
        self.conn = await pool.getconn()
        # pgvector registration per connection (idempotent)
        register_vector(self.conn)
        self.conn.autocommit = self.autocommit
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.conn is None:
            return
        try:
            if exc_type is not None:
                await self.conn.rollback()
            elif not self.autocommit:
                await self.conn.commit()
        except Exception:
            await self.conn.rollback()
        finally:
            get_pool().putconn(self.conn)
            self.conn = None

    # ── Core async query methods ───────────────────────────────────────────────
    async def fetchone(self, query: str, params: tuple | dict | None = None) -> dict | None:
        """Return first row or None."""
        async with self.conn.cursor() as cur:
            await cur.execute(query, params)
            result = await cur.fetchone()
            return dict(result) if result else None

    async def fetchall(self, query: str, params: tuple | dict | None = None) -> list[dict]:
        """Return all rows as list of dicts."""
        async with self.conn.cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

    async def execute(self, query: str, params: tuple | dict | None = None) -> None:
        """Execute a query (INSERT/UPDATE/DELETE)."""
        async with self.conn.cursor() as cur:
            await cur.execute(query, params)

    async def execute_scalar(self, query: str, params: tuple | dict | None = None) -> Any:
        """Return first column of first row (e.g. COUNT, SUM)."""
        async with self.conn.cursor() as cur:
            await cur.execute(query, params)
            row = await cur.fetchone()
            return row[0] if row else None

    async def execute_returning(self, query: str, params: tuple | dict | None = None) -> dict | None:
        """Execute INSERT ... RETURNING * and return the row dict."""
        async with self.conn.cursor() as cur:
            await cur.execute(query, params)
            result = await cur.fetchone()
            return dict(result) if result else None

    async def execute_many(self, query: str, params_list: list[tuple]) -> int:
        """Execute many rows. Returns rowcount."""
        async with self.conn.cursor() as cur:
            await cur.executemany(query, params_list)
            return cur.rowcount


# ── Module-level async convenience functions ────────────────────────────────────

async def pg_fetchone(query: str, params: tuple | dict | None = None) -> dict | None:
    async with AsyncPgSession() as s:
        return await s.fetchone(query, params)


async def pg_fetchall(query: str, params: tuple | dict | None = None) -> list[dict]:
    async with AsyncPgSession() as s:
        return await s.fetchall(query, params)


async def pg_execute(query: str, params: tuple | dict | None = None) -> None:
    async with AsyncPgSession() as s:
        await s.execute(query, params)


async def pg_exists(query: str, params: tuple | dict | None = None) -> bool:
    """Return True if query returns at least one row."""
    row = await pg_fetchone(query, params)
    return row is not None


async def pg_scalar(query: str, params: tuple | dict | None = None) -> Any:
    return await pg_fetchone(query, params)


# ── Backward-compat sync wrappers (DEPRECATED) ────────────────────────────────
# These exist only to avoid breaking non-async callers during migration.
# All async callers should use the async functions above directly.

import threading  # noqa: E402
import asyncio  # noqa: E402

_sync_lock = threading.Lock()


def _run_async(coro):
    """Run an async coroutine from sync context using a new event loop."""
    try:
        loop = asyncio.get_running_loop()
        # Already in async context — shouldn't happen in sync wrappers, but guard:
        raise RuntimeError("Cannot call _run_async from within an async context")
    except RuntimeError:
        # No running loop — create one
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _sync_wrapper(async_func):
    """Wrap an async function with a sync interface using a thread pool."""
    def wrapper(*args, **kwargs):
        coro = async_func(*args, **kwargs)
        return _run_async(coro)
    return wrapper


# Deprecated sync variants — prefer migrating callers to async instead
pg_fetchone_sync       = _sync_wrapper(pg_fetchone)
pg_fetchall_sync       = _sync_wrapper(pg_fetchall)
pg_execute_sync        = _sync_wrapper(pg_execute)
pg_exists_sync         = _sync_wrapper(pg_exists)
pg_scalar_sync         = _sync_wrapper(pg_scalar)

# Backward compat: keep PgSession name as alias to AsyncPgSession
# (but callers must migrate to AsyncPgSession + await)
PgSession = AsyncPgSession
