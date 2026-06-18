---
name: db-facade-proxy-standard
description: |
  Standard for the `_proxy` / `_proxy_async` programmatic-staticmethod
  pattern used by `app/db/facade.py` and `app/memory/db_memory_facade.py`.
  Covers when to add a new passthrough, when to write a hand-rolled wrapper
  instead, naming conventions, docstring preservation, and how to keep the
  two facades in sync with their underlying `_models` / `_db_memory` layers.
  Use when adding a new method to a facade, or when refactoring an existing
  facade method. Does NOT cover: the SQL constants in `queries.py`, the
  pgvector schema, async session management, or tool-level memory writes
  (see `memory-embedding-pipeline-standard`).
---

# DB Facade Proxy Standard

> **Scope**: `app/db/facade.py` and `app/memory/db_memory_facade.py`.
> **Authority**: Subordinate to `yuzu-db-architecture` (Constitution §1-4).
> The two facades mirror the pattern; any rule here applies to both.

---

## 1. When to Use `_proxy` vs Hand-Rolled Method

**Use `_proxy` / `_proxy_async` when:**

- The underlying function's signature is acceptable as-is for the facade surface.
- No argument normalization is needed (no reordering, no defaulting, no transformation).
- No additional side effects are required (no logging, no caching, no validation).

**Hand-roll a method when:**

- The function needs argument reordering (e.g., `Database.add_message` puts `role`/`content` first; the underlying `add_message` takes `session_id` first).
- The method needs a default (e.g., falling back to the active session).
- The method needs to combine multiple underlying calls.
- The method has docstring or behavior that must differ from the underlying function.

**Anti-pattern (DO NOT):**

- Hand-rolling a 1-line passthrough "for clarity" — it duplicates 200+ lines that the proxy helpers were created to avoid.
- Using `_proxy` on a function whose signature you actually want to normalize — the proxy forwards verbatim, no normalization happens.

---

## 2. The Proxy Helpers

Both facades define these two helpers (verbatim, byte-identical):

```python
def _proxy(target: Callable[..., Any]) -> staticmethod:
    """Wrap a sync function in a staticmethod that forwards *args/**kwargs."""

    def _call(*args: Any, **kwargs: Any) -> Any:
        return target(*args, **kwargs)

    _call.__name__ = target.__name__
    _call.__doc__ = target.__doc__
    return staticmethod(_call)


def _proxy_async(target: Callable[..., Any]) -> staticmethod:
    """Wrap an async function in a staticmethod that forwards *args/**kwargs."""

    async def _call(*args: Any, **kwargs: Any) -> Any:
        return await target(*args, **kwargs)

    _call.__name__ = target.__name__
    _call.__doc__ = target.__doc__
    return staticmethod(_call)
```

**Rules:**

- These helpers MUST be byte-identical between the two facades. If you change one, change the other in the same commit.
- `_call.__name__` and `_call.__doc__` preservation is mandatory — it keeps the facade surface introspectable and lets `help(Database.foo)` show the underlying function's signature.
- Do NOT add caching, logging, or retry to `_proxy` — keep it pure. If you need those, hand-roll.

---

## 3. Adding a New Facade Method

Step-by-step (sync facade example for `app/db/facade.py`):

1. **Underlying layer:** add the function to `app/db/models.py` (or extend an existing one).
2. **Async mirror:** add `_async` variant to `app/db/models_async.py` with the same signature (Constitution §4: async is mandatory).
3. **Import:** at the top of the facade, add the import:
   ```python
   from app.db.models import new_function as _pg_new_function
   from app.db.models_async import new_function_async as _pg_new_function_async
   ```
4. **Attach to the class:** inside the class body, add the proxy lines:
   ```python
   new_function = _proxy(_pg_new_function)
   new_function_async = _proxy_async(_pg_new_function_async)
   ```
5. **No additional code.** The class body is the only place these appear.

**Anti-pattern (DO NOT):**

- Defining `_pg_new_function` only in `models.py` and skipping the `_async` mirror — every sync method MUST have an async equivalent.
- Wrapping the proxy in another function for "type hints" — staticmethod's type is already exposed.
- Adding the method to the facade but not to the underlying model — the facade is a passthrough, not a definition site.

---

## 4. Naming and Visibility

- Underlying function names: `snake_case`, with `_async` suffix for the async variant.
- Imported aliases in the facade: `_pg_<name>` (for `db/facade.py`) or `_<name>` (for `memory/db_memory_facade.py`). The leading underscore + facade-specific prefix prevents accidental re-export.
- Exposed method names: identical to the underlying function (no prefix, no rename). The proxy preserves `__name__`.

**Anti-pattern (DO NOT):**

- Renaming in the facade (`new_function` → `add_new_thing`) — breaks the "single source of truth" property of the facade.
- Re-exporting `_pg_new_function` directly in `__all__` — the facade re-exports the public name, not the alias.

---

## 5. Hand-Rolled Method Skeleton

When you need normalization, follow this pattern (example from `Database.add_message`):

```python
@staticmethod
async def add_message_async(
    role: str,
    content: str,
    session_id: int | None = None,
    **kwargs: Any,
) -> int | None:
    """Docstring that documents the facade's normalized signature.

    The underlying `_pg_add_message_async` takes session_id first; this
    method puts role/content first and defaults session_id to the active
    session.
    """
    if session_id is None:
        session_id = (await _pg_get_active_session_async())["id"]
    return await _pg_add_message_async(
        session_id=session_id, role=role, content=content, **kwargs
    )
```

**Rules:**

- `@staticmethod` decorator (these are staticmethod-style facade methods, not classmethods).
- Type hints on the public method (Constitution: `from __future__ import annotations` + modern syntax).
- Docstring describes the normalized surface, not the underlying call.
- The defaulting logic is local to the facade — do not move it to the underlying model.

**Anti-pattern (DO NOT):**

- Making hand-rolled methods `classmethod` — they don't use `cls` and would break the static call sites.
- Calling the sync underlying from an `async def` facade method — always call the `_async` variant.
- Adding `**kwargs: Any` "just in case" — be explicit about the normalized surface.

---

## 6. Keeping the Two Facades in Sync

`app/db/facade.py` and `app/memory/db_memory_facade.py` follow the same pattern but serve different domains. They MUST NOT import from each other.

**Rules:**

- `app/db/facade.py` proxies methods from `app/db/models.py` and `app/db/models_async.py`.
- `app/memory/db_memory_facade.py` proxies methods from `app/memory/db_memory.py` (which itself uses `app/db/connection.py`).
- If a memory operation needs a general DB operation, call `Database.<method>()` from the memory facade — do not duplicate the logic in memory layer.
- The `_proxy` and `_proxy_async` helpers are defined independently in each facade. Do NOT import them from a shared utility (the byte-identical constraint is enforced by review, not by import).

**Anti-pattern (DO NOT):**

- Putting a memory-specific method in `app/db/facade.py` — memory lives in its own facade.
- Putting a generic DB method (e.g., `get_active_session`) in `app/memory/db_memory_facade.py` — that's `Database`'s job.

---

## 7. SQL Constants Re-Export

Both facades re-export SQL constants from their respective `queries.py` modules:

```python
from app.memory.db_memory_queries import (
    FACT_TYPE_STATIC,
    FACT_TYPE_DYNAMIC,
    EMBEDDING_DIM,
)
```

**Rules:**

- Re-exported constants keep their original names (no `MEMORY_FACT_TYPE_STATIC` rename).
- Add new constants here if they need to be referenced by callers via the facade.
- Do NOT re-export SQL query strings (`SQL_*`) — those are for the underlying layer only.

**Anti-pattern (DO NOT):**

- Importing the constant from `db_memory_queries` directly in a tool — go through the facade so the constant has one definition site.

---

## 8. Pre-Push Checklist for Facade Changes

- [ ] Both `_proxy` and `_proxy_async` remain byte-identical if you touched either
- [ ] New sync method has an `_async` mirror
- [ ] Proxy lines are inside the class body, not module-level
- [ ] No new dependencies added (Constitution: dependency surface is intentionally minimal)
- [ ] `ruff check .` and `python3 -m py_compile app/db/facade.py app/memory/db_memory_facade.py` pass
- [ ] If you changed a docstring or signature: the underlying model's docstring is also updated (single source of truth)
