# FILE: app/db_pg.py
# DESCRIPTION: PostgreSQL connection pool and raw SQL helpers.
#             psycopg v3 async pool (AsyncConnectionPool).
#             Sync wrappers provided for backward compatibility during migration.

from __future__ import annotations

import asyncio
import atexit
import os
from typing import Any

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

# ── Env defaults ────────────────────────────────────────────────────────────
_PG_HOST = os.getenv("PGHOST", os.getenv("PG_HOST", "127.0.0.1"))
_PG_PORT = os.getenv("PGPORT", os.getenv("PG_PORT", "5432"))
_PG_DBNAME = os.getenv("PGDATABASE", os.getenv("PG_DBNAME", "yuzuki"))
_PG_USER = os.getenv("PGUSER", os.getenv("PG_USER", "icedeyes12"))
_PG_PASSWORD = os.getenv("PGPASSWORD", os.getenv("PG_PASSWORD", ""))
_MIN_CONN = 1
_MAX_CONN = 10


# ── Vector literal formatting (pgvector uses square brackets) ───────────────
def vector_sql(val: list[float] | None) -> str | None:
    """Convert list[float] to pgvector literal string."""
    if val is None:
        return None
    return "[" + ",".join(str(x) for x in val) + "]"


# ── DSN builder ──────────────────────────────────────────────────────────────
def _build_dsn() -> str:
    return (
        f"host={_PG_HOST} port={_PG_PORT} dbname={_PG_DBNAME} "
        f"user={_PG_USER} password={_PG_PASSWORD}"
    )


# ── Global async pool (lazy singleton) ───────────────────────────────────────
_async_pool: AsyncConnectionPool | None = None


async def get_async_pool() -> AsyncConnectionPool:
    """Get or create the async connection pool."""
    global _async_pool
    if _async_pool is None:
        _async_pool = AsyncConnectionPool(
            conninfo=_build_dsn(),
            min_size=_MIN_CONN,
            max_size=_MAX_CONN,
            kwargs={"row_factory": dict_row},
        )
        await _async_pool.open()
        print(f"[db_pg] Async pool created: {_PG_HOST}:{_PG_PORT}/{_PG_DBNAME}")
    return _async_pool


async def close_async_pool() -> None:
    """Close the async connection pool."""
    global _async_pool
    if _async_pool is not None:
        await _async_pool.close()
        _async_pool = None
        print("[db_pg] Async pool closed")


# Register cleanup on exit
atexit.register(lambda: asyncio.run(close_async_pool()) if _async_pool else None)


# ── Async Session Context Manager ────────────────────────────────────────────
class AsyncPgSession:
    """
    Async context manager for database sessions.
    Commits on success, rolls back on exception.

    Usage:
        async with AsyncPgSession() as s:
            row = await s.fetchone("SELECT * FROM profiles LIMIT 1")
            await s.execute("INSERT INTO ...")
    """

    __slots__ = ("conn", "autocommit", "_pool")

    def __init__(self, autocommit: bool = False):
        self.autocommit = autocommit
        self.conn = None
        self._pool = None

    async def __aenter__(self) -> "AsyncPgSession":
        self._pool = await get_async_pool()
        self.conn = await self._pool.get_connection()
        if self.autocommit:
            await self.conn.set_autocommit(True)
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
            await self._pool.put_connection(self.conn)
            self.conn = None

    # ── Core query methods ─────────────────────────────────────────────────
    async def fetchone(self, query: str, params: tuple | dict | None = None) -> dict | None:
        """Return first row or None."""
        async with self.conn.cursor() as cur:
            await cur.execute(query, params)
            row = await cur.fetchone()
            return dict(row) if row else None

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
            row = await cur.fetchone()
            return dict(row) if row else None

    async def execute_batch(self, query: str, params_list: list[tuple]) -> int:
        """Execute many rows. Returns rowcount."""
        async with self.conn.cursor() as cur:
            await cur.executemany(query, params_list)
            return cur.rowcount or 0


# ── Module-level async convenience functions ──────────────────────────────────
async def pg_fetchone_async(query: str, params: tuple | dict | None = None) -> dict | None:
    async with AsyncPgSession() as s:
        return await s.fetchone(query, params)


async def pg_fetchall_async(query: str, params: tuple | dict | None = None) -> list[dict]:
    async with AsyncPgSession() as s:
        return await s.fetchall(query, params)


async def pg_execute_async(query: str, params: tuple | dict | None = None) -> None:
    async with AsyncPgSession() as s:
        await s.execute(query, params)


async def pg_exists_async(query: str, params: tuple | dict | None = None) -> bool:
    return await pg_fetchone_async(query, params) is not None


async def pg_scalar_async(query: str, params: tuple | dict | None = None) -> Any:
    return await pg_fetchone_async(query, params)


# ── SYNC WRAPPERS (for backward compatibility during migration) ──────────────
# These run async functions in a sync context using asyncio.run()
# WARNING: Only use in non-async contexts. Prefer async versions in async code.


def _run_async(coro):
    """Run async coroutine in sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're in an async context but called sync function
        # This is a common mistake during migration
        raise RuntimeError(
            "Sync DB function called from async context. "
            "Use the _async version instead (e.g., pg_fetchone_async)."
        )
    return asyncio.run(coro)


def pg_fetchone(query: str, params: tuple | dict | None = None) -> dict | None:
    return _run_async(pg_fetchone_async(query, params))


def pg_fetchall(query: str, params: tuple | dict | None = None) -> list[dict]:
    return _run_async(pg_fetchall_async(query, params))


def pg_execute(query: str, params: tuple | dict | None = None) -> None:
    _run_async(pg_execute_async(query, params))


def pg_exists(query: str, params: tuple | dict | None = None) -> bool:
    return _run_async(pg_exists_async(query, params))


def pg_scalar(query: str, params: tuple | dict | None = None) -> Any:
    return _run_async(pg_scalar_async(query, params))


# ── Legacy sync context manager (DEPRECATED) ─────────────────────────────────
class PgSession:
    """
    DEPRECATED: Sync context manager for backward compatibility.
    Use AsyncPgSession in async code.

    This is a thin wrapper that runs async operations synchronously.
    """

    __slots__ = ("autocommit", "_session")

    def __init__(self, autocommit: bool = False):
        self.autocommit = autocommit
        self._session = None

    def __enter__(self) -> "PgSession":
        # Create async session and run its __aenter__
        self._session = AsyncPgSession(autocommit=self.autocommit)
        # Can't use context manager in sync context, so we create a new event loop
        loop = asyncio.new_event_loop()
        try:
            self._session.conn = loop.run_until_complete(
                (asyncio.get_event_loop_policy()
                 .get_event_loop()
                 .run_until_complete(get_async_pool()))
                .get_connection()
            )
            if self.autocommit:
                loop.run_until_complete(self._session.conn.set_autocommit(True))
        finally:
            loop.close()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._session is None or self._session.conn is None:
            return
        loop = asyncio.new_event_loop()
        try:
            if exc_type is not None:
                loop.run_until_complete(self._session.conn.rollback())
            elif not self.autocommit:
                loop.run_until_complete(self._session.conn.commit())
        finally:
            loop.close()

    def fetchone(self, query: str, params: tuple | dict | None = None) -> dict | None:
        return _run_async(self._session.fetchone(query, params)) if self._session else None

    def fetchall(self, query: str, params: tuple | dict | None = None) -> list[dict]:
        return _run_async(self._session.fetchall(query, params)) if self._session else []

    def execute(self, query: str, params: tuple | dict | None = None) -> None:
        if self._session:
            _run_async(self._session.execute(query, params))

    def execute_scalar(self, query: str, params: tuple | dict | None = None) -> Any:
        return _run_async(self._session.execute_scalar(query, params)) if self._session else None

    def execute_returning(self, query: str, params: tuple | dict | None = None) -> dict | None:
        return _run_async(self._session.execute_returning(query, params)) if self._session else None

    def execute_batch(self, query: str, params_list: list[tuple]) -> int:
        return _run_async(self._session.execute_batch(query, params_list)) if self._session else 0


# ── Pool management (for compatibility) ──────────────────────────────────────
def get_pool():
    """DEPRECATED: Use get_async_pool() instead."""
    return _run_async(get_async_pool())


def close_pool():
    """DEPRECATED: Use close_async_pool() instead."""
    _run_async(close_async_pool())
