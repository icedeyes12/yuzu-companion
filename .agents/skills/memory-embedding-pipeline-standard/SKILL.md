---
name: memory-embedding-pipeline-standard
description: |
  Standard for the memory embedding pipeline in yuzu-companion.
  Covers transport (Chutes-hosted Qwen3-Embedding-8B endpoint), dimension
  contract (4096-dim float), rate-limit sharing with the LLM Chutes provider,
  embedder module location, and integration with the
  `MemoryDB.search_similar_async` retrieval path. Use when modifying
  `app/memory/embedder.py`, swapping the embedding model, debugging
  pgvector dimension mismatches, or changing the rate-limit budget for
  concurrent embedding + LLM calls. Does NOT cover: SQL queries for
  semantic_facts, the FSRS decay pipeline, profile analysis, or tool
  memory_store (which delegates here).
---

# Memory Embedding Pipeline Standard

> **Scope**: `app/memory/embedder.py` and its callers in the memory subsystem.
> **Authority**: This skill is subordinate to `yuzu-db-architecture` (Constitution) and the dimension/model rules in it.

---

## 1. The Dimension Contract Is Sacred

The `semantic_facts` table's `embedding` column is **`vector(4096)`**. Any change here is a multi-step migration that touches the schema, the embedder, the search path, and re-embedding all existing facts.

**Hard rules:**

- `app/memory/embedder.py` MUST define `EMBEDDING_DIM = 4096` as a module-level constant.
- The same constant MUST be re-exported from `app/memory/db_memory_queries.py` and `app/memory/db_memory_facade.py` for caller convenience.
- Any vector column that stores embeddings MUST be `vector(4096)` — drift is a hard error.
- The pgvector distance operator (`<=>`, `<->`) MUST use the 4096-dim vectors as-is. Do NOT project, truncate, or pad.

**Why:** pgvector stores dimension at column-definition time. Changing the dimension requires `ALTER TABLE ... ALTER COLUMN embedding TYPE vector(4096)` with `USING` clause, plus a re-embed of every fact (see `scripts/reembed_all.py` — hands-off per Constitution).

---

## 2. Transport Is Chutes-Hosted Qwen3

The model name **`Qwen3-Embedding-8B`** is hosted on Chutes at a model-specific endpoint. There is NO local model.

**Endpoint constant** (in `app/memory/embedder.py`):

```python
CHUTES_EMBED_ENDPOINT = (
    "https://chutes-qwen-qwen3-embedding-8b-tee.chutes.ai/v1/embeddings"
)
```

**Rules:**

- The endpoint is model-specific. The `model` field in the payload is sent as `None` (the server ignores it). Do NOT add a `model` parameter to the embedder public API unless you also re-point the endpoint to a different Chutes deployment.
- The embedder uses the same Chutes API key as the LLM Chutes provider. Resolve it via `get_ai_manager()` → `manager.providers["chutes"].api_key`. Do NOT add a separate API key field.
- Auth header: `Authorization: Bearer <chutes_api_key>`. Use the same key as the LLM Chutes path.

**Anti-pattern (DO NOT):**

- Calling the original `Qwen/Qwen3-Embedding-8B` model via the generic `/v1/chat/completions` endpoint.
- Adding a second `EMBEDDING_API_KEY` env var.
- Hitting the embedder from a worker pool with its own key — always go through the singleton's API key.

---

## 3. Rate-Limit Sharing With the LLM Path

The embedder and the LLM Chutes provider share the same upstream Chutes account, so 429s on one will spill to the other if not coordinated.

**The contract:**

- `embed_texts_async()` MUST acquire the provider-level rate-limit semaphore via `async with _rate_limit_provider("chutes", candidate_model, source="embedding"):` before each HTTP call.
- The `source` argument to `_rate_limit_provider` MUST be `"embedding"` (or another non-`"llm"` tag) so logs and metrics can disambiguate embedding vs LLM pressure.
- The same `asyncio.Semaphore(1)` per provider, recreated per event loop (see `app/providers/base.py:_get_provider_semaphore_async`).
- Between sequential embed batches in a loop, the semaphore releases naturally — do not add manual `asyncio.sleep()` between batches. The semaphore + provider delay already enforces pacing.

**Anti-pattern (DO NOT):**

- Bypassing `_rate_limit_provider` because "this is a different API endpoint" — it isn't, the rate limit is per-Chutes-account, not per-endpoint.
- Adding a per-text semaphore that serializes individual HTTP calls inside one batch.
- Adding a separate `_rate_limit_embedding` function — the existing provider rate limit already covers embeddings.

---

## 4. Embedder Public API

The embedder exposes ONE public async function:

```python
async def embed_texts_async(
    texts: list[str] | str,
    *,
    model: str | None = None,        # ignored — endpoint is model-specific
    dimensions: int | None = None,   # ignored — fixed at 4096
    encoding_format: str = "float",
    timeout: int = 30,
) -> list[list[float]]:
    ...
```

**Rules:**

- `texts` is normalized to `list[str]`; an empty list returns `[]` immediately without calling the API.
- Return is a list of 4096-length float lists, in the same order as input.
- `timeout` is per-batch (the whole `texts` list), not per-text. Do not split long batches — pass them whole and let the server chunk.
- Errors raise `RuntimeError("Chutes API key not configured")` if the key is missing, or propagate `httpx` errors otherwise. Do NOT swallow errors silently.

**Anti-pattern (DO NOT):**

- Adding a sync `embed_texts()` variant — the memory pipeline is fully async.
- Returning numpy arrays or torch tensors — keep it `list[list[float]]` for psycopg2 compatibility.
- Adding caching at the embedder level — `app/memory/retrieval.py` already has thread-local embedding cache.

---

## 5. Callers: Who Embeds and Why

Only these callers should invoke `embed_texts_async()`:

| Caller | Purpose | Frequency |
|---|---|---|
| `app/tools/memory_store.py` | Embed a new fact before insert | Per fact |
| `app/memory/db_memory.py:save_fact_async` | Embed a programmatic fact write | Per fact |
| `app/memory/extractor.py` | Batch-embed candidate facts after segmentation | Per pipeline run (every 5th turn, throttled) |
| `app/memory/retrieval.py` | Embed a user query for similarity search | Per turn (cached thread-locally) |

**Anti-pattern (DO NOT):**

- Embedding inside `app/orchestrator.py` directly — go through `memory_store` tool or `MemoryDB.save_fact_async`.
- Embedding the same text twice in a single turn — the retrieval cache in `app/memory/retrieval.py` already deduplicates per query string.
- Embedding the assistant's reply for "memory" — the pipeline only embeds user-facing facts and segmentation candidates.

---

## 6. The Embedder Is Not a Facade

Unlike `db/facade.py` and `memory/db_memory_facade.py`, the embedder is a **leaf module** — it does its own HTTP and is not a proxy over a lower layer. This is intentional: there is no separate `embedder_async.py`.

**Rules:**

- No `_proxy` / `_proxy_async` pattern here. Direct implementation.
- If you need to swap the embedding model in the future, change the endpoint constant AND re-embed all facts (touching `scripts/reembed_all.py`, which is hands-off per Constitution). Do not add a runtime model-selector flag.

---

## 7. Pre-Push Checklist for Embedding Changes

Before committing any change to `app/memory/embedder.py` or any caller of `embed_texts_async`:

- [ ] `EMBEDDING_DIM = 4096` still defined and unchanged
- [ ] `CHUTES_EMBED_ENDPOINT` still points to the Qwen3 deployment
- [ ] `embed_texts_async` still uses `_rate_limit_provider("chutes", ..., source="embedding")`
- [ ] No new env vars, no new keys, no new model selector
- [ ] If the schema changed: migration script in `scripts/` (hands-off — flag the user before running)
- [ ] `ruff check .` and `python3 -m py_compile app/memory/embedder.py` both pass
- [ ] If dimension changed: full re-embed plan documented, with the user explicitly approving `scripts/reembed_all.py`
