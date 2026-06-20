# FILE: tests/test_skill_memory_embedding_pipeline_standard.py
# DESCRIPTION: Tests validating that app/memory/embedder.py and its callers
#              conform to the rules documented in
#              .agents/skills/memory-embedding-pipeline-standard/SKILL.md.
#
# The skill mandates:
#   - EMBEDDING_DIM = 4096 in embedder.py (section 1)
#   - EMBEDDING_DIM re-exported from db_memory_queries.py (section 1)
#   - EMBEDDING_DIM re-exported from db_memory_facade.py (section 1)
#   - CHUTES_EMBED_ENDPOINT points to Qwen3 endpoint (section 2)
#   - DEFAULT_MODEL is None / endpoint is model-specific (section 2)
#   - embed_texts_async raises RuntimeError when API key missing (section 4)
#   - embed_texts_async returns [] for empty input (section 4)
#   - embed_texts_async normalizes a bare string to [str] (section 4)
#   - embed_texts_async uses _rate_limit_provider with source="embedding" (section 3)
#   - No sync embed_texts() is the primary API — async is the canonical path (section 4)
#   - Embedder is a leaf module (no _proxy / _proxy_async pattern) (section 6)
#   - Dimension mismatch raises ValueError (section 4 / section 1)

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.memory.embedder as embedder_module
from app.memory.embedder import (
    CHUTES_EMBED_ENDPOINT,
    EMBEDDING_DIM,
    embed_texts_async,
)


# ---------------------------------------------------------------------------
# Section 1: The Dimension Contract
# ---------------------------------------------------------------------------


class TestDimensionContract:
    """EMBEDDING_DIM must be 4096 everywhere it is defined or re-exported."""

    def test_embedder_dim_is_4096(self):
        assert embedder_module.EMBEDDING_DIM == 4096

    def test_db_memory_queries_dim_is_4096(self):
        from app.memory.db_memory_queries import EMBEDDING_DIM as q_dim
        assert q_dim == 4096

    def test_db_memory_facade_dim_is_4096(self):
        from app.memory.db_memory_facade import EMBEDDING_DIM as f_dim
        assert f_dim == 4096

    def test_dim_is_int_not_float(self):
        assert isinstance(embedder_module.EMBEDDING_DIM, int)

    def test_dim_is_module_level_constant(self):
        """EMBEDDING_DIM must be accessible as a module attribute."""
        assert hasattr(embedder_module, "EMBEDDING_DIM")

    def test_all_three_dim_constants_agree(self):
        from app.memory.db_memory_queries import EMBEDDING_DIM as q_dim
        from app.memory.db_memory_facade import EMBEDDING_DIM as f_dim
        assert embedder_module.EMBEDDING_DIM == q_dim == f_dim


# ---------------------------------------------------------------------------
# Section 2: Transport — Chutes-hosted Qwen3 endpoint
# ---------------------------------------------------------------------------


class TestEndpointContract:
    """The endpoint constant must point to the Qwen3 Chutes deployment."""

    def test_endpoint_is_module_level_constant(self):
        assert hasattr(embedder_module, "CHUTES_EMBED_ENDPOINT")

    def test_endpoint_is_chutes_qwen3(self):
        expected = (
            "https://chutes-qwen-qwen3-embedding-8b-tee.chutes.ai/v1/embeddings"
        )
        assert CHUTES_EMBED_ENDPOINT == expected

    def test_endpoint_uses_https(self):
        assert CHUTES_EMBED_ENDPOINT.startswith("https://")

    def test_endpoint_targets_embeddings_path(self):
        assert CHUTES_EMBED_ENDPOINT.endswith("/v1/embeddings")

    def test_default_model_is_none(self):
        """The model field is server-side-specific; DEFAULT_MODEL must be None."""
        assert embedder_module.DEFAULT_MODEL is None

    def test_endpoint_does_not_point_to_chat_completions(self):
        """Must NOT be the generic chat endpoint."""
        assert "chat/completions" not in CHUTES_EMBED_ENDPOINT


# ---------------------------------------------------------------------------
# Section 4: Public API — embed_texts_async behaviour
# ---------------------------------------------------------------------------


def _fake_client_context(embeddings: list[list[float]]):
    """Build a mock httpx.AsyncClient context that returns fake embeddings."""
    data_items = [{"embedding": emb} for emb in embeddings]
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": data_items}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    # Support `async with client:` context manager protocol
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestEmbedTextsAsync:
    """Tests for embed_texts_async() public API (section 4)."""

    def test_empty_list_returns_empty_without_api_call(self):
        """Empty input must return [] immediately — no HTTP call."""
        with patch.object(
            embedder_module, "_get_client", new=AsyncMock(return_value=MagicMock())
        ):
            result = asyncio.run(embed_texts_async([]))
        assert result == []

    def test_empty_string_normalised_to_single_item_list(self):
        """A bare str must be treated as [str]."""
        # We only check the normalisation step; stub out the HTTP call.
        good_embedding = [0.0] * EMBEDDING_DIM
        mock_client = _fake_client_context([good_embedding])

        with (
            patch.object(embedder_module, "_get_client", new=AsyncMock(return_value=mock_client)),
            patch.object(embedder_module, "_rate_limit_provider") as mock_rl,
        ):
            mock_rl.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_rl.return_value.__aexit__ = AsyncMock(return_value=False)
            result = asyncio.run(embed_texts_async("hello world"))
        # The call succeeded and returned one embedding
        assert len(result) == 1
        assert len(result[0]) == EMBEDDING_DIM

    def test_raises_runtime_error_when_no_api_key(self):
        """RuntimeError must be raised (not swallowed) when API key is absent."""
        with patch.object(embedder_module, "_get_client", new=AsyncMock(return_value=None)):
            with pytest.raises(RuntimeError, match="Chutes API key not configured"):
                asyncio.run(embed_texts_async(["some text"]))

    def test_returns_list_of_float_lists(self):
        """Return type must be list[list[float]] (no numpy, no tensors)."""
        good_emb = [float(i) / EMBEDDING_DIM for i in range(EMBEDDING_DIM)]
        mock_client = _fake_client_context([good_emb])

        with (
            patch.object(embedder_module, "_get_client", new=AsyncMock(return_value=mock_client)),
            patch.object(embedder_module, "_rate_limit_provider") as mock_rl,
        ):
            mock_rl.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_rl.return_value.__aexit__ = AsyncMock(return_value=False)
            result = asyncio.run(embed_texts_async(["foo"]))
        assert isinstance(result, list)
        assert isinstance(result[0], list)
        assert all(isinstance(v, float) for v in result[0])

    def test_dimension_mismatch_raises_value_error(self):
        """If the API returns wrong-dim vectors, ValueError must be raised."""
        wrong_dim_emb = [0.0] * 128  # Not 4096
        mock_client = _fake_client_context([wrong_dim_emb])

        with (
            patch.object(embedder_module, "_get_client", new=AsyncMock(return_value=mock_client)),
            patch.object(embedder_module, "_rate_limit_provider") as mock_rl,
        ):
            mock_rl.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_rl.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ValueError, match="Embedding dim mismatch"):
                asyncio.run(embed_texts_async(["bar"]))

    def test_result_preserves_input_order(self):
        """Return must match input order."""
        emb_a = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
        emb_b = [0.0] * (EMBEDDING_DIM - 1) + [1.0]
        mock_client = _fake_client_context([emb_a, emb_b])

        with (
            patch.object(embedder_module, "_get_client", new=AsyncMock(return_value=mock_client)),
            patch.object(embedder_module, "_rate_limit_provider") as mock_rl,
        ):
            mock_rl.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_rl.return_value.__aexit__ = AsyncMock(return_value=False)
            result = asyncio.run(embed_texts_async(["first", "second"]))
        assert result[0] == emb_a
        assert result[1] == emb_b

    def test_timeout_kwarg_is_forwarded_to_http_call(self):
        """The timeout parameter must be passed to client.post()."""
        good_emb = [0.0] * EMBEDDING_DIM
        mock_client = _fake_client_context([good_emb])

        with (
            patch.object(embedder_module, "_get_client", new=AsyncMock(return_value=mock_client)),
            patch.object(embedder_module, "_rate_limit_provider") as mock_rl,
        ):
            mock_rl.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_rl.return_value.__aexit__ = AsyncMock(return_value=False)
            asyncio.run(embed_texts_async(["x"], timeout=60))

        call_kwargs = mock_client.post.call_args
        assert call_kwargs is not None
        # timeout=60 must appear in the call
        assert call_kwargs.kwargs.get("timeout") == 60 or (
            len(call_kwargs.args) >= 2 and 60 in call_kwargs.args
        )


# ---------------------------------------------------------------------------
# Section 3: Rate-limit sharing — source tag must be "embedding"
# ---------------------------------------------------------------------------


class TestRateLimitIntegration:
    """embed_texts_async must use _rate_limit_provider with source='embedding'."""

    def test_rate_limit_provider_called_with_chutes(self):
        """Provider arg to _rate_limit_provider must be 'chutes'."""
        good_emb = [0.0] * EMBEDDING_DIM
        mock_client = _fake_client_context([good_emb])
        rate_limit_calls = []

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_rate_limit(provider, model, source="llm"):
            rate_limit_calls.append((provider, model, source))
            yield

        with (
            patch.object(embedder_module, "_get_client", new=AsyncMock(return_value=mock_client)),
            patch.object(embedder_module, "_rate_limit_provider", fake_rate_limit),
        ):
            asyncio.run(embed_texts_async(["test text"]))

        assert len(rate_limit_calls) == 1
        provider, model, source = rate_limit_calls[0]
        assert provider == "chutes"

    def test_rate_limit_source_is_embedding(self):
        """source arg to _rate_limit_provider must be 'embedding'."""
        good_emb = [0.0] * EMBEDDING_DIM
        mock_client = _fake_client_context([good_emb])
        rate_limit_calls = []

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_rate_limit(provider, model, source="llm"):
            rate_limit_calls.append((provider, model, source))
            yield

        with (
            patch.object(embedder_module, "_get_client", new=AsyncMock(return_value=mock_client)),
            patch.object(embedder_module, "_rate_limit_provider", fake_rate_limit),
        ):
            asyncio.run(embed_texts_async(["test text"]))

        _, _, source = rate_limit_calls[0]
        assert source == "embedding", (
            f"source must be 'embedding', not '{source}'"
        )

    def test_rate_limit_not_bypassed_for_empty_input(self):
        """Empty input returns early before rate limit is even needed."""
        rate_limit_calls = []

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_rate_limit(provider, model, source="llm"):
            rate_limit_calls.append((provider, model, source))
            yield

        with (
            patch.object(embedder_module, "_get_client", new=AsyncMock(return_value=MagicMock())),
            patch.object(embedder_module, "_rate_limit_provider", fake_rate_limit),
        ):
            result = asyncio.run(embed_texts_async([]))

        assert result == []
        # Rate limit must NOT be called for an empty-input no-op
        assert rate_limit_calls == []


# ---------------------------------------------------------------------------
# Section 4: No caching at embedder level
# ---------------------------------------------------------------------------


class TestNoCachingAtEmbedderLevel:
    """Embedder must call the API every time — caching is retrieval.py's job."""

    def test_two_calls_with_same_text_both_hit_api(self):
        good_emb = [0.0] * EMBEDDING_DIM
        mock_client = _fake_client_context([good_emb, good_emb])
        # We need two separate clients for two calls
        mock_client2 = _fake_client_context([good_emb])
        clients = [mock_client, mock_client2]
        call_count = [0]

        async def fake_get_client():
            idx = call_count[0] % 2
            call_count[0] += 1
            return clients[idx]

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_rl(provider, model, source="llm"):
            yield

        with (
            patch.object(embedder_module, "_get_client", fake_get_client),
            patch.object(embedder_module, "_rate_limit_provider", fake_rl),
        ):
            asyncio.run(embed_texts_async(["same text"]))
            asyncio.run(embed_texts_async(["same text"]))

        # Both calls must go through _get_client (not cached)
        assert call_count[0] == 2


# ---------------------------------------------------------------------------
# Section 6: Embedder is a leaf module (no _proxy pattern)
# ---------------------------------------------------------------------------


class TestEmbedderIsLeafModule:
    """The embedder must NOT use the _proxy/_proxy_async facade pattern."""

    def test_no_proxy_helper_in_embedder(self):
        assert not hasattr(embedder_module, "_proxy"), (
            "embedder.py must not define _proxy — it is a leaf module"
        )

    def test_no_proxy_async_helper_in_embedder(self):
        assert not hasattr(embedder_module, "_proxy_async"), (
            "embedder.py must not define _proxy_async — it is a leaf module"
        )

    def test_embed_texts_async_is_defined_directly_in_module(self):
        """embed_texts_async is defined in embedder.py, not proxied from elsewhere."""
        import inspect
        fn = getattr(embedder_module, "embed_texts_async", None)
        assert fn is not None
        # It must be defined in this module, not imported from another
        assert inspect.getmodule(fn).__name__ == "app.memory.embedder"

    def test_no_embedder_async_submodule(self):
        """There must be no separate embedder_async.py module."""
        embedder_async_path = ROOT / "app" / "memory" / "embedder_async.py"
        assert not embedder_async_path.exists(), (
            "embedder_async.py must not exist — embedder is a leaf module with direct impl"
        )


# ---------------------------------------------------------------------------
# Regression / boundary: dimension constant is never 0 or negative
# ---------------------------------------------------------------------------


class TestDimensionBoundary:
    def test_embedding_dim_positive(self):
        assert EMBEDDING_DIM > 0

    def test_embedding_dim_not_zero(self):
        assert EMBEDDING_DIM != 0

    def test_embedding_dim_is_power_of_two_or_qwen_standard(self):
        """4096 is a known Qwen3-Embedding-8B output dimension."""
        assert EMBEDDING_DIM == 4096, (
            "Dimension changed from 4096 — this requires a full schema migration"
        )