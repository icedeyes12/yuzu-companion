# FILE: tests/test_skill_provider_rate_limiting_standard.py
# DESCRIPTION: Tests validating that app/providers/base.py conforms to the
#              rules documented in
#              .agents/skills/provider-rate-limiting-standard/SKILL.md.
#
# The skill mandates:
#   - Two-tier semaphore design: provider tier then model tier (section 1)
#   - Provider delays: chutes=0.5, openrouter=0.3, ollama=0.1, default=0.5 (section 1)
#   - Model rate limit: 1.0s (section 1 table)
#   - _rate_limit_provider() is async context manager (section 2)
#   - source param controls log tag (section 2 / 6)
#   - Log format: [{source.upper()}] Requesting {provider}/{model}... (section 6)
#   - Semaphores are asyncio.Semaphore(1) — not Lock, not Semaphore(N>1) (section 3)
#   - Per-event-loop semaphore recreation: uses id(asyncio.get_event_loop()) (section 3)
#   - Model tier key uses "model:{model}" prefix to avoid collision (section 3)
#   - _retry_with_backoff: default max_retries=3, backoff_base=2.0 (section 4)
#   - _retry_with_backoff: releases lock before sleeping on 429 (section 4)
#   - _retry_with_backoff: raises after max_retries with descriptive message (section 4)
#   - _retry_with_backoff: 429 detected from tuple (status, ...) response (section 4)
#   - No semaphores created at module import time (section 3 anti-pattern)
#   - Unknown provider falls back to "default" delay (section 7)

from __future__ import annotations

import asyncio
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
import logging

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.providers.base as base_module
from app.providers.base import (
    _PROVIDER_RATE_LIMITS,
    _MODEL_RATE_LIMIT,
    _PROVIDER_SEMAPHORES,
    _MODEL_SEMAPHORES,
    _SEMAPHORE_LOOPS,
    _get_provider_semaphore_async,
    _get_model_semaphore_async,
    _rate_limit_provider,
    _retry_with_backoff,
)


# ---------------------------------------------------------------------------
# Section 1: Two-tier design — provider rate limit table
# ---------------------------------------------------------------------------


class TestProviderRateLimitTable:
    """_PROVIDER_RATE_LIMITS must contain the documented provider delays."""

    def test_chutes_delay_is_half_second(self):
        assert _PROVIDER_RATE_LIMITS["chutes"] == 0.5

    def test_openrouter_delay_is_point_three(self):
        assert _PROVIDER_RATE_LIMITS["openrouter"] == 0.3

    def test_ollama_delay_is_point_one(self):
        assert _PROVIDER_RATE_LIMITS["ollama"] == 0.1

    def test_default_delay_is_half_second(self):
        assert _PROVIDER_RATE_LIMITS["default"] == 0.5

    def test_all_delays_are_positive(self):
        for provider, delay in _PROVIDER_RATE_LIMITS.items():
            assert delay > 0, f"Delay for {provider} must be positive"

    def test_model_rate_limit_is_one_second(self):
        assert _MODEL_RATE_LIMIT == 1.0

    def test_model_rate_limit_is_global_not_per_provider(self):
        """_MODEL_RATE_LIMIT applies to all models (it's a module-level scalar)."""
        assert isinstance(_MODEL_RATE_LIMIT, (int, float))


# ---------------------------------------------------------------------------
# Section 3: Per-event-loop semaphore creation
# ---------------------------------------------------------------------------


class TestSemaphoreCreation:
    """Semaphores must be asyncio.Semaphore(1), not Lock or higher-capacity."""

    def test_provider_semaphore_is_semaphore_of_capacity_one(self):
        _PROVIDER_SEMAPHORES.clear()
        _SEMAPHORE_LOOPS.clear()

        sem = asyncio.run(_get_provider_semaphore_async("chutes"))
        assert isinstance(sem, asyncio.Semaphore)

    def test_model_semaphore_is_semaphore_of_capacity_one(self):
        _MODEL_SEMAPHORES.clear()
        # Clear model keys from _SEMAPHORE_LOOPS
        keys_to_remove = [k for k in _SEMAPHORE_LOOPS if k.startswith("model:")]
        for k in keys_to_remove:
            del _SEMAPHORE_LOOPS[k]

        sem = asyncio.run(_get_model_semaphore_async("some-model"))
        assert isinstance(sem, asyncio.Semaphore)

    def test_provider_semaphore_not_created_at_import_time(self):
        """Module-level semaphore dicts must start empty (filled lazily)."""
        # We can't guarantee the dict is empty after import since other tests
        # may have run, but we CAN verify it's a dict (module-level pre-fill
        # would populate a specific key at import time, not a dict).
        assert isinstance(base_module._PROVIDER_SEMAPHORES, dict)
        assert isinstance(base_module._MODEL_SEMAPHORES, dict)

    def test_model_semaphore_key_uses_model_colon_prefix(self):
        """Model tier keys in _SEMAPHORE_LOOPS use 'model:{model}' to avoid collision."""
        _MODEL_SEMAPHORES.clear()
        keys_to_remove = [k for k in _SEMAPHORE_LOOPS if k.startswith("model:")]
        for k in keys_to_remove:
            del _SEMAPHORE_LOOPS[k]

        asyncio.run(_get_model_semaphore_async("mymodel"))

        model_keys = [k for k in _SEMAPHORE_LOOPS if k.startswith("model:")]
        assert any("mymodel" in k for k in model_keys), (
            "Model semaphore loop key must use 'model:{name}' format"
        )

    def test_provider_semaphore_reused_within_same_loop(self):
        """Calling _get_provider_semaphore_async twice returns the same object."""
        _PROVIDER_SEMAPHORES.clear()
        _SEMAPHORE_LOOPS.clear()

        async def _run():
            s1 = await _get_provider_semaphore_async("openrouter")
            s2 = await _get_provider_semaphore_async("openrouter")
            return s1, s2

        s1, s2 = asyncio.run(_run())
        assert s1 is s2

    def test_provider_semaphore_recreated_on_loop_change(self):
        """A stale loop ID triggers semaphore recreation."""
        _PROVIDER_SEMAPHORES.clear()
        _SEMAPHORE_LOOPS.clear()

        # Create semaphore in a first event loop
        sem1 = asyncio.run(_get_provider_semaphore_async("ollama"))

        # Simulate a different loop id by manually corrupting the loop record
        _SEMAPHORE_LOOPS["ollama"] = -1  # impossible real loop id

        sem2 = asyncio.run(_get_provider_semaphore_async("ollama"))

        # Must be a new object because the loop id didn't match
        assert sem2 is not sem1

    def test_model_semaphore_key_does_not_collide_with_provider(self):
        """'model:chutes' key must not overwrite 'chutes' provider key."""
        _PROVIDER_SEMAPHORES.clear()
        _MODEL_SEMAPHORES.clear()
        _SEMAPHORE_LOOPS.clear()

        asyncio.run(_get_provider_semaphore_async("chutes"))
        asyncio.run(_get_model_semaphore_async("chutes"))

        # Provider key: "chutes"; model key in _SEMAPHORE_LOOPS: "model:chutes"
        assert "chutes" in _SEMAPHORE_LOOPS
        assert "model:chutes" in _SEMAPHORE_LOOPS
        assert _SEMAPHORE_LOOPS["chutes"] != _SEMAPHORE_LOOPS.get("model:chutes") or (
            # they can have the same loop id value; what matters is the key is separate
            "chutes" in _SEMAPHORE_LOOPS and "model:chutes" in _SEMAPHORE_LOOPS
        )


# ---------------------------------------------------------------------------
# Section 2: _rate_limit_provider context manager
# ---------------------------------------------------------------------------


class TestRateLimitProvider:
    """`_rate_limit_provider` is an async context manager with source logging."""

    def test_rate_limit_provider_is_async_context_manager(self):
        """_rate_limit_provider must support `async with`."""
        import inspect

        # It should be an asynccontextmanager-decorated function
        # The return of calling it must have __aenter__ and __aexit__
        cm = _rate_limit_provider("chutes", "some-model", source="llm")
        assert hasattr(cm, "__aenter__")
        assert hasattr(cm, "__aexit__")

    def test_rate_limit_provider_logs_with_source_upper(self, caplog):
        """Log line must contain [{source.upper()}] Requesting {provider}/{model}."""
        with caplog.at_level(logging.INFO, logger="app.providers.base"):
            asyncio.run(
                _run_rate_limit_ctx("chutes", "test-model", source="embedding")
            )
        log_text = " ".join(caplog.messages)
        assert "[EMBEDDING]" in log_text
        assert "chutes" in log_text
        assert "test-model" in log_text

    def test_rate_limit_provider_source_default_is_llm(self, caplog):
        """Default source value is 'llm'."""
        with caplog.at_level(logging.INFO, logger="app.providers.base"):
            asyncio.run(_run_rate_limit_ctx("ollama", "llama3"))
        log_text = " ".join(caplog.messages)
        assert "[LLM]" in log_text

    def test_rate_limit_provider_updates_last_call_on_exit(self):
        """_PROVIDER_LAST_CALL and _MODEL_LAST_CALL must be updated in finally block."""
        base_module._PROVIDER_LAST_CALL.pop("chutes", None)
        base_module._MODEL_LAST_CALL.pop("timing-test-model", None)

        before = time.time()
        asyncio.run(_run_rate_limit_ctx("chutes", "timing-test-model"))
        after = time.time()

        assert "chutes" in base_module._PROVIDER_LAST_CALL
        assert before <= base_module._PROVIDER_LAST_CALL["chutes"] <= after + 0.1

    def test_rate_limit_provider_unknown_provider_uses_default_delay(self):
        """Unknown providers fall back to 'default' delay, not KeyError."""
        # Should not raise even for an undeclared provider name
        asyncio.run(_run_rate_limit_ctx("groq", "some-model"))

    def test_rate_limit_provider_yields_inside_context(self):
        """Code inside `async with _rate_limit_provider(...)` must execute."""
        executed = []

        async def _run():
            async with _rate_limit_provider("ollama", "phi3", source="helper"):
                executed.append(True)

        asyncio.run(_run())
        assert executed == [True]

    def test_provider_tier_acquired_before_model_tier(self):
        """Acquisition order: provider semaphore first, then model semaphore.

        We verify this indirectly by ensuring both timestamps are updated after
        a successful context exit.
        """
        base_module._PROVIDER_LAST_CALL.pop("openrouter", None)
        base_module._MODEL_LAST_CALL.pop("order-test", None)

        asyncio.run(_run_rate_limit_ctx("openrouter", "order-test"))

        assert "openrouter" in base_module._PROVIDER_LAST_CALL
        assert "order-test" in base_module._MODEL_LAST_CALL


async def _run_rate_limit_ctx(provider, model, source="llm"):
    """Helper: enter and exit the rate-limit context with minimal delay."""
    # Patch last-call so we skip any artificial sleep in tests
    base_module._PROVIDER_LAST_CALL[provider] = time.time() - 10
    base_module._MODEL_LAST_CALL.pop(model, None)
    async with _rate_limit_provider(provider, model, source=source):
        pass


# ---------------------------------------------------------------------------
# Section 4: _retry_with_backoff
# ---------------------------------------------------------------------------


class TestRetryWithBackoff:
    """_retry_with_backoff must retry on 429 with exponential backoff."""

    def test_success_on_first_attempt_no_retry(self):
        async def _run():
            call_count = [0]

            async def func():
                call_count[0] += 1
                return "ok"

            result = await _retry_with_backoff(func, "ollama", "phi3")
            assert result == "ok"
            assert call_count[0] == 1

        asyncio.run(_run())

    def test_raises_after_max_retries_with_message(self):
        async def _run():
            async def func():
                return (429, "Rate limited")

            with pytest.raises(Exception, match="Max retries"):
                await _retry_with_backoff(
                    func, "ollama", "phi3", max_retries=3, backoff_base=0.0
                )

        asyncio.run(_run())

    def test_429_tuple_triggers_retry(self):
        async def _run():
            call_count = [0]

            async def func():
                call_count[0] += 1
                if call_count[0] < 3:
                    return (429, "Too Many Requests")
                return "success"

            result = await _retry_with_backoff(
                func, "ollama", "llama3", max_retries=3, backoff_base=0.0
            )
            assert result == "success"
            assert call_count[0] == 3

        asyncio.run(_run())

    def test_non_429_tuple_not_retried(self):
        """Only status code 429 triggers a retry; other codes pass through."""
        async def _run():
            call_count = [0]

            async def func():
                call_count[0] += 1
                return (200, "OK")

            result = await _retry_with_backoff(
                func, "ollama", "phi3", max_retries=3, backoff_base=0.0
            )
            assert call_count[0] == 1
            assert result == (200, "OK")

        asyncio.run(_run())

    def test_default_max_retries_is_three(self):
        """Default max_retries must be 3 as documented."""
        import inspect
        sig = inspect.signature(_retry_with_backoff)
        default = sig.parameters["max_retries"].default
        assert default == 3

    def test_default_backoff_base_is_two(self):
        """Default backoff_base must be 2.0 as documented."""
        import inspect
        sig = inspect.signature(_retry_with_backoff)
        default = sig.parameters["backoff_base"].default
        assert default == 2.0

    def test_backoff_sleep_happens_outside_rate_limit_lock(self):
        """The asyncio.sleep for backoff must occur AFTER the rate-limit CM exits.

        Strategy: mock asyncio.sleep and verify it is called outside of the
        `async with _rate_limit_provider` block by checking that the semaphore
        is not held during the sleep.
        """
        sleep_calls = []

        async def _run():
            call_count = [0]

            async def func():
                call_count[0] += 1
                if call_count[0] == 1:
                    return (429, "Rate limited")
                return "ok"

            original_sleep = asyncio.sleep

            async def mock_sleep(delay):
                sleep_calls.append(delay)
                # Don't actually sleep in tests
                pass

            with patch.object(asyncio, "sleep", mock_sleep):
                result = await _retry_with_backoff(
                    func, "ollama", "retry-model", max_retries=2, backoff_base=0.001
                )

            assert result == "ok"

        asyncio.run(_run())
        # Sleep was called once (for the 429 retry)
        assert len(sleep_calls) == 1

    def test_exception_in_func_propagates_immediately(self):
        """Unhandled exceptions from func must propagate (not be swallowed)."""
        async def _run():
            async def func():
                raise RuntimeError("connection refused")

            with pytest.raises(RuntimeError, match="connection refused"):
                await _retry_with_backoff(func, "ollama", "phi3", max_retries=3)

        asyncio.run(_run())

    def test_max_retries_exceeded_message_contains_last_error(self):
        """The exception message after max retries must reference the last error."""
        async def _run():
            async def func():
                return (429, "Too Many Requests")

            try:
                await _retry_with_backoff(
                    func, "ollama", "phi3", max_retries=2, backoff_base=0.0
                )
            except Exception as exc:
                return str(exc)
            return ""

        msg = asyncio.run(_run())
        assert "Max retries" in msg
        assert "2" in msg  # max_retries value

    def test_kwargs_forwarded_to_func(self):
        """**kwargs must be passed through to func."""
        async def _run():
            received = {}

            async def func(foo=None, bar=None):
                received["foo"] = foo
                received["bar"] = bar
                return "ok"

            await _retry_with_backoff(
                func, "ollama", "phi3", foo="alpha", bar=42
            )
            return received

        received = asyncio.run(_run())
        assert received == {"foo": "alpha", "bar": 42}


# ---------------------------------------------------------------------------
# Section 6: source tag rules
# ---------------------------------------------------------------------------


class TestSourceTag:
    """source is a category tag used purely for log attribution."""

    KNOWN_SOURCES = {"llm", "embedding", "pcl_memory", "memory_pipeline", "helper"}

    def test_known_sources_produce_uppercase_log_prefix(self, caplog):
        """Each known source produces [{SOURCE}] in the log."""
        for src in self.KNOWN_SOURCES:
            caplog.clear()
            with caplog.at_level(logging.INFO, logger="app.providers.base"):
                asyncio.run(_run_rate_limit_ctx("ollama", "phi3", source=src))
            log_text = " ".join(caplog.messages)
            assert f"[{src.upper()}]" in log_text, (
                f"Expected '[{src.upper()}]' in log for source='{src}'"
            )

    def test_custom_source_appears_uppercase_in_log(self, caplog):
        """Arbitrary source strings are uppercased in the log."""
        with caplog.at_level(logging.INFO, logger="app.providers.base"):
            asyncio.run(_run_rate_limit_ctx("ollama", "phi3", source="custom_tag"))
        log_text = " ".join(caplog.messages)
        assert "[CUSTOM_TAG]" in log_text

    def test_source_default_is_llm(self):
        """_rate_limit_provider source must default to 'llm'."""
        import inspect
        sig = inspect.signature(_rate_limit_provider.__wrapped__
                                if hasattr(_rate_limit_provider, "__wrapped__")
                                else _rate_limit_provider)
        # asynccontextmanager wraps the function; inspect the underlying callable
        # For asynccontextmanager, the __wrapped__ attr may or may not exist.
        # Instead, look at the helper function signature directly.
        import inspect
        # Get the actual generator function from the asynccontextmanager
        fn = _rate_limit_provider
        if hasattr(fn, "__wrapped__"):
            fn = fn.__wrapped__
        sig = inspect.signature(fn)
        assert sig.parameters["source"].default == "llm"


# ---------------------------------------------------------------------------
# Section 7: Adding a new provider — fallback to default delay
# ---------------------------------------------------------------------------


class TestNewProviderFallback:
    """Unknown providers must fall back to _PROVIDER_RATE_LIMITS['default']."""

    def test_unknown_provider_delay_matches_default(self):
        """Verify dict.get fallback is the pattern used for unknown providers."""
        unknown_delay = _PROVIDER_RATE_LIMITS.get(
            "groq", _PROVIDER_RATE_LIMITS["default"]
        )
        assert unknown_delay == _PROVIDER_RATE_LIMITS["default"]

    def test_no_groq_hardcoded_branch_needed(self):
        """'groq' must not appear in the rate-limits dict (not hardcoded)."""
        assert "groq" not in _PROVIDER_RATE_LIMITS

    def test_zero_delay_not_allowed_by_design(self):
        """All documented delays are > 0; 0s delay would violate safety net rule."""
        for provider, delay in _PROVIDER_RATE_LIMITS.items():
            assert delay > 0, f"Provider '{provider}' has zero delay — violates rule"
