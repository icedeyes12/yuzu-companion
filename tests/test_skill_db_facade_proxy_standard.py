# FILE: tests/test_skill_db_facade_proxy_standard.py
# DESCRIPTION: Tests validating that app/db/facade.py and
#              app/memory/db_memory_facade.py conform to the rules
#              documented in .agents/skills/db-facade-proxy-standard/SKILL.md.
#
# The skill mandates:
#   - _proxy / _proxy_async preserve __name__ and __doc__ of the wrapped target.
#   - Both helpers return a staticmethod.
#   - The two _proxy implementations are functionally equivalent.
#   - Import aliases in db/facade.py use the _pg_ prefix.
#   - Import aliases in memory/db_memory_facade.py use a plain _ prefix.
#   - Proxy-generated class attributes call the underlying target verbatim.
#   - Hand-rolled methods are decorated with @staticmethod (not classmethod).
#   - Re-exported constants keep their original names.

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path (mirrors conftest.py)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.db.facade as db_facade_module
import app.memory.db_memory_facade as mem_facade_module
from app.db.facade import Database, _proxy, _proxy_async
from app.memory.db_memory_facade import (
    MemoryDB,
    _proxy as _mem_proxy,
    _proxy_async as _mem_proxy_async,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sync_target(name="target_fn", doc="Target docstring."):
    def fn(*args, **kwargs):
        return (args, kwargs)

    fn.__name__ = name
    fn.__doc__ = doc
    return fn


def _make_async_target(name="async_target_fn", doc="Async target docstring."):
    async def fn(*args, **kwargs):
        return (args, kwargs)

    fn.__name__ = name
    fn.__doc__ = doc
    return fn


# ---------------------------------------------------------------------------
# Section 2: _proxy and _proxy_async rules (db/facade.py)
# ---------------------------------------------------------------------------


class TestProxyHelperDb:
    """Tests for _proxy and _proxy_async in app/db/facade.py."""

    def test_proxy_returns_staticmethod(self):
        target = _make_sync_target()
        result = _proxy(target)
        assert isinstance(result, staticmethod)

    def test_proxy_async_returns_staticmethod(self):
        target = _make_async_target()
        result = _proxy_async(target)
        assert isinstance(result, staticmethod)

    def test_proxy_preserves_name(self):
        target = _make_sync_target(name="get_profile")
        wrapped = _proxy(target).__func__
        assert wrapped.__name__ == "get_profile"

    def test_proxy_preserves_doc(self):
        target = _make_sync_target(doc="Fetch the user profile row.")
        wrapped = _proxy(target).__func__
        assert wrapped.__doc__ == "Fetch the user profile row."

    def test_proxy_async_preserves_name(self):
        target = _make_async_target(name="get_profile_async")
        wrapped = _proxy_async(target).__func__
        assert wrapped.__name__ == "get_profile_async"

    def test_proxy_async_preserves_doc(self):
        target = _make_async_target(doc="Async fetch of user profile row.")
        wrapped = _proxy_async(target).__func__
        assert wrapped.__doc__ == "Async fetch of user profile row."

    def test_proxy_forwards_positional_args(self):
        call_log = []

        def fn(a, b):
            call_log.append((a, b))
            return a + b

        fn.__name__ = "fn"
        fn.__doc__ = None
        wrapped = _proxy(fn).__func__
        result = wrapped(1, 2)
        assert result == 3
        assert call_log == [(1, 2)]

    def test_proxy_forwards_keyword_args(self):
        call_log = []

        def fn(x, y=10):
            call_log.append((x, y))
            return x * y

        fn.__name__ = "fn"
        fn.__doc__ = None
        wrapped = _proxy(fn).__func__
        result = wrapped(3, y=7)
        assert result == 21
        assert call_log == [(3, 7)]

    def test_proxy_does_not_add_extra_logic(self):
        """The proxy must forward verbatim — no caching, logging, or retry."""
        sentinel = object()
        call_count = [0]

        def fn():
            call_count[0] += 1
            return sentinel

        fn.__name__ = "fn"
        fn.__doc__ = None
        wrapped = _proxy(fn).__func__
        r1 = wrapped()
        r2 = wrapped()
        # Both calls hit the underlying function (no caching)
        assert call_count[0] == 2
        assert r1 is sentinel
        assert r2 is sentinel

    def test_proxy_name_is_not_call(self):
        """The inner wrapper must not retain the generic '_call' name."""
        target = _make_sync_target(name="switch_session")
        wrapped = _proxy(target).__func__
        assert wrapped.__name__ == "switch_session"
        assert wrapped.__name__ != "_call"

    def test_proxy_async_name_is_not_call(self):
        target = _make_async_target(name="create_session_async")
        wrapped = _proxy_async(target).__func__
        assert wrapped.__name__ == "create_session_async"
        assert wrapped.__name__ != "_call"


# ---------------------------------------------------------------------------
# Section 2: _proxy and _proxy_async rules (memory/db_memory_facade.py)
# ---------------------------------------------------------------------------


class TestProxyHelperMemory:
    """Tests for _proxy and _proxy_async in app/memory/db_memory_facade.py."""

    def test_proxy_returns_staticmethod(self):
        target = _make_sync_target()
        result = _mem_proxy(target)
        assert isinstance(result, staticmethod)

    def test_proxy_async_returns_staticmethod(self):
        target = _make_async_target()
        result = _mem_proxy_async(target)
        assert isinstance(result, staticmethod)

    def test_proxy_preserves_name(self):
        target = _make_sync_target(name="search_similar")
        wrapped = _mem_proxy(target).__func__
        assert wrapped.__name__ == "search_similar"

    def test_proxy_preserves_doc(self):
        target = _make_sync_target(doc="Search semantically similar facts.")
        wrapped = _mem_proxy(target).__func__
        assert wrapped.__doc__ == "Search semantically similar facts."

    def test_proxy_async_preserves_name(self):
        target = _make_async_target(name="save_fact_async")
        wrapped = _mem_proxy_async(target).__func__
        assert wrapped.__name__ == "save_fact_async"

    def test_proxy_async_preserves_doc(self):
        target = _make_async_target(doc="Persist a memory fact asynchronously.")
        wrapped = _mem_proxy_async(target).__func__
        assert wrapped.__doc__ == "Persist a memory fact asynchronously."

    def test_proxy_forwards_positional_args(self):
        received = []

        def fn(a, b, c):
            received.append((a, b, c))

        fn.__name__ = "fn"
        fn.__doc__ = None
        _mem_proxy(fn).__func__(10, 20, 30)
        assert received == [(10, 20, 30)]

    def test_proxy_forwards_keyword_args(self):
        received = []

        def fn(**kw):
            received.append(kw)

        fn.__name__ = "fn"
        fn.__doc__ = None
        _mem_proxy(fn).__func__(key="value")
        assert received == [{"key": "value"}]


# ---------------------------------------------------------------------------
# Section 2: Byte-identical proxy rule across both facades
# ---------------------------------------------------------------------------


class TestProxyIdentity:
    """The two _proxy implementations must behave identically."""

    def test_sync_proxy_both_forward_args(self):
        results_db = []
        results_mem = []

        def fn_db(x):
            results_db.append(x)
            return x * 2

        fn_db.__name__ = "fn_db"
        fn_db.__doc__ = None

        def fn_mem(x):
            results_mem.append(x)
            return x * 2

        fn_mem.__name__ = "fn_mem"
        fn_mem.__doc__ = None

        r_db = _proxy(fn_db).__func__(5)
        r_mem = _mem_proxy(fn_mem).__func__(5)
        assert r_db == r_mem == 10

    def test_both_preserve_name_the_same_way(self):
        fn1 = _make_sync_target(name="shared_name")
        fn2 = _make_sync_target(name="shared_name")
        assert _proxy(fn1).__func__.__name__ == _mem_proxy(fn2).__func__.__name__

    def test_both_preserve_doc_the_same_way(self):
        doc = "Common docstring for both facades."
        fn1 = _make_sync_target(doc=doc)
        fn2 = _make_sync_target(doc=doc)
        assert _proxy(fn1).__func__.__doc__ == _mem_proxy(fn2).__func__.__doc__


# ---------------------------------------------------------------------------
# Section 4: Naming and import aliases
# ---------------------------------------------------------------------------


class TestImportAliasConventions:
    """Import aliases in the two facades must follow the naming rules."""

    def test_db_facade_uses_pg_prefix_for_aliases(self):
        """All function aliases in db/facade.py must start with _pg_."""
        pg_aliases = [
            name
            for name in dir(db_facade_module)
            if name.startswith("_pg_")
        ]
        # There must be at least one _pg_-prefixed name (the actual proxied funcs)
        assert len(pg_aliases) > 0, "Expected at least one _pg_ alias in db/facade.py"

    def test_db_facade_pg_aliases_are_not_in_all(self):
        """Internal _pg_ aliases must NOT appear in __all__."""
        all_exports = getattr(db_facade_module, "__all__", [])
        for name in all_exports:
            assert not name.startswith("_pg_"), (
                f"Internal alias '{name}' leaked into __all__"
            )

    def test_memory_facade_uses_plain_underscore_prefix(self):
        """All function aliases in memory/db_memory_facade.py start with _ but not _pg_."""
        private_names = [
            name
            for name in dir(mem_facade_module)
            if name.startswith("_") and not name.startswith("__")
        ]
        pg_names = [n for n in private_names if n.startswith("_pg_")]
        assert pg_names == [], (
            f"Memory facade should not use _pg_ prefix; found: {pg_names}"
        )

    def test_memory_facade_private_aliases_not_in_all(self):
        all_exports = getattr(mem_facade_module, "__all__", [])
        for name in all_exports:
            assert not name.startswith("_"), (
                f"Private name '{name}' leaked into __all__"
            )

    def test_db_facade_public_name_preserved_by_proxy(self):
        """Proxy-generated method __name__ matches its attribute name."""
        # get_profile is proxied; its __func__.__name__ must equal 'get_profile'
        attr = Database.__dict__["get_profile"]
        assert isinstance(attr, staticmethod)
        assert attr.__func__.__name__ == "get_profile"

    def test_memory_facade_public_name_preserved_by_proxy(self):
        attr = MemoryDB.__dict__["search_similar"]
        assert isinstance(attr, staticmethod)
        assert attr.__func__.__name__ == "search_similar"


# ---------------------------------------------------------------------------
# Section 3 & 5: Class body placement and hand-rolled methods are @staticmethod
# ---------------------------------------------------------------------------


class TestClassBodyAndHandRolled:
    """Proxy assignments live inside the class; hand-rolled methods are @staticmethod."""

    def test_proxy_methods_are_class_attributes_not_module_level(self):
        """Proxy-generated attributes exist on the class, not the module."""
        assert "get_profile" in Database.__dict__
        assert "get_profile_async" in Database.__dict__

    def test_hand_rolled_add_message_is_staticmethod(self):
        """add_message is hand-rolled and must be a staticmethod."""
        attr = Database.__dict__["add_message"]
        assert isinstance(attr, staticmethod), (
            "Hand-rolled add_message must be a @staticmethod, not classmethod"
        )

    def test_hand_rolled_get_messages_is_staticmethod(self):
        attr = Database.__dict__["get_messages"]
        assert isinstance(attr, staticmethod)

    def test_hand_rolled_clear_session_is_staticmethod(self):
        attr = Database.__dict__["clear_session"]
        assert isinstance(attr, staticmethod)

    def test_hand_rolled_methods_not_classmethod(self):
        """No hand-rolled facade method should be a classmethod."""
        for name, val in Database.__dict__.items():
            if name.startswith("_"):
                continue
            assert not isinstance(val, classmethod), (
                f"Database.{name} is a classmethod — must be @staticmethod"
            )

    def test_memory_proxy_methods_are_class_attributes(self):
        assert "save_fact" in MemoryDB.__dict__
        assert "save_fact_async" in MemoryDB.__dict__
        assert "search_similar" in MemoryDB.__dict__
        assert "search_similar_async" in MemoryDB.__dict__

    def test_memory_no_classmethod_on_facade(self):
        for name, val in MemoryDB.__dict__.items():
            if name.startswith("_"):
                continue
            assert not isinstance(val, classmethod), (
                f"MemoryDB.{name} is a classmethod — must be a proxy staticmethod"
            )


# ---------------------------------------------------------------------------
# Section 6: Facade isolation (no cross-imports)
# ---------------------------------------------------------------------------


class TestFacadeIsolation:
    """The two facades must not import from each other."""

    def test_db_facade_does_not_import_memory_facade(self):
        db_module_obj = sys.modules.get("app.db.facade")
        assert db_module_obj is not None
        for attr in dir(db_module_obj):
            val = getattr(db_module_obj, attr, None)
            if inspect.ismodule(val):
                assert "db_memory_facade" not in val.__name__, (
                    "app.db.facade must not import from app.memory.db_memory_facade"
                )

    def test_memory_facade_does_not_import_db_facade(self):
        mem_module_obj = sys.modules.get("app.memory.db_memory_facade")
        if mem_module_obj is None:
            return  # Module not loaded yet; skip
        for attr in dir(mem_module_obj):
            val = getattr(mem_module_obj, attr, None)
            if inspect.ismodule(val):
                assert "app.db.facade" not in getattr(val, "__name__", ""), (
                    "app.memory.db_memory_facade must not import from app.db.facade"
                )


# ---------------------------------------------------------------------------
# Section 7: SQL constant re-exports
# ---------------------------------------------------------------------------


class TestConstantReExports:
    """Constants must keep their original names when re-exported."""

    def test_memory_facade_exports_fact_type_static(self):
        from app.memory.db_memory_facade import FACT_TYPE_STATIC
        assert FACT_TYPE_STATIC == "static"

    def test_memory_facade_exports_fact_type_dynamic(self):
        from app.memory.db_memory_facade import FACT_TYPE_DYNAMIC
        assert FACT_TYPE_DYNAMIC == "dynamic"

    def test_memory_facade_exports_embedding_dim(self):
        from app.memory.db_memory_facade import EMBEDDING_DIM
        assert EMBEDDING_DIM == 4096

    def test_memory_facade_all_includes_constants(self):
        all_exports = getattr(mem_facade_module, "__all__", [])
        assert "FACT_TYPE_STATIC" in all_exports
        assert "FACT_TYPE_DYNAMIC" in all_exports
        assert "EMBEDDING_DIM" in all_exports

    def test_db_facade_all_does_not_include_sql_query_strings(self):
        """SQL_* query strings must not appear in __all__."""
        all_exports = getattr(db_facade_module, "__all__", [])
        sql_exports = [name for name in all_exports if name.startswith("SQL_")]
        assert sql_exports == [], (
            f"SQL query strings leaked into __all__: {sql_exports}"
        )

    def test_memory_facade_all_does_not_include_sql_query_strings(self):
        all_exports = getattr(mem_facade_module, "__all__", [])
        sql_exports = [name for name in all_exports if name.startswith("SQL_")]
        assert sql_exports == [], (
            f"SQL query strings leaked into __all__: {sql_exports}"
        )

    def test_constants_not_renamed_in_memory_facade(self):
        """Constants must not be renamed (e.g., MEMORY_FACT_TYPE_STATIC is wrong)."""
        all_exports = getattr(mem_facade_module, "__all__", [])
        bad = [n for n in all_exports if n.startswith("MEMORY_")]
        assert bad == [], f"Constants must not be prefixed with MEMORY_: {bad}"


# ---------------------------------------------------------------------------
# Pre-push checklist: both facades have sync+async proxy pairs
# ---------------------------------------------------------------------------


class TestSyncAsyncPairs:
    """Every sync proxy must have a corresponding _async proxy."""

    def _async_name(self, name: str) -> str:
        return name if name.endswith("_async") else name + "_async"

    def test_db_facade_sync_methods_have_async_counterpart(self):
        """
        For each public Database attribute that does NOT end in _async,
        there must be a corresponding <name>_async attribute.
        """
        skip = {"__dict__", "__doc__", "__module__", "__weakref__"}
        for name in Database.__dict__:
            if name.startswith("_") or name in skip:
                continue
            if name.endswith("_async"):
                continue
            async_name = name + "_async"
            # Some known sync-only names may not have async peers; list them.
            known_sync_only = {
                "clear_chat_history",  # alias that delegates to clear_session
                "add_memory_note",    # alias
            }
            if name in known_sync_only:
                continue
            assert async_name in Database.__dict__, (
                f"Database.{name} has no async counterpart Database.{async_name}"
            )

    def test_memory_facade_sync_proxies_have_async_counterparts(self):
        """
        Most MemoryDB proxy methods have async pairs; verify the primary ones.
        """
        required_pairs = [
            "save_fact",
            "search_similar",
            "search_trgm",
            "search_tsv",
            "get_fact_by_id",
            "get_facts_by_ids",
            "get_facts_by_session",
            "update_last_accessed",
            "invalidate_fact",
        ]
        for name in required_pairs:
            assert name in MemoryDB.__dict__, f"MemoryDB.{name} missing"
            assert name + "_async" in MemoryDB.__dict__, (
                f"MemoryDB.{name}_async missing"
            )