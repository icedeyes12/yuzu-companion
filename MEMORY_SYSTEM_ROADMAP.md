# yuzu-companion Memory System Roadmap

> Last updated: 2026-03-25

## Status: Phase A Complete ✅

### Architecture (Existing)

| Layer | File | Status |
|---|---|---|
| Raw messages | `messages` table | ✅ |
| Segmentation | `app/memory/segmenter.py` | ✅ |
| Episodic summary | `app/memory/extractor.py` | ✅ |
| Semantic triples | `app/memory/extractor.py` | ✅ |
| Cosine retrieval | `app/memory/retrieval.py` | ✅ |
| FSRS decay | `app/memory/review.py` | ✅ |
| Per-message extraction | `app/app.py:on_message` | ✅ |
| Session init wiring | `app/app.py:start_chat_session` | ✅ |
| Memory context injection | `app/app.py:handle_user_message_streaming` | ✅ |

## Implemented (Phase A)

- **[A1]** `hnswlib` → not installable in this env. Replaced with `scipy.spatial.cKDTree` + `joblib` (both pre-installed). Updated `requirements.txt`.
- **[A2]** `app/memory/index_store.py` created — `NNIndex` (cKDTree cosine ANN) + `IndexStore` (per-session, persisted to disk via joblib).
- **[A3]** `retrieval.py` rewritten — ANN fast path (cKDTree) + DB fallback. O(n) full-scan removed.
- **[A4]** Index is rebuilt from DB on session startup (app.py:start_chat_session). Note: upserts from extractor.py are not yet synced to the live index (see A4 remaining).
- **[A5]** Session startup calls `store.rebuild()` after memory init.
- **[A6]** `idx_semantic_entity` already exists in database.py.

## Remaining

```
[A4] Sync upserts from extractor.py to live index
  └── When upsert_semantic_memory() / create_episodic_memory() are called,
      they should call index_store.add_*() to update the in-memory index.
      Currently the index is rebuilt from DB each session — correct but not real-time.

[B]  Quality & Dedupe
  ├── [ ] B1. Upsert dedupe key: (entity, relation, target) — already done in extractor.py ✅
  ├── [ ] B2. memory_store.py uses exact match dedupe — add cosine fallback (>0.95) to extractor path too
  └── [ ] B3. Add idempotency key to process_messages_for_memory

[C]  Observability
  ├── [ ] C1. Add memory stats endpoint: counts per type, index size, last decay time
  ├── [ ] C2. Log retrieval latency + result count in retrieval.py
  └── [ ] C3. Log HNSW index rebuild time on startup

[D]  Testing
  ├── [ ] D1. Test: 1000 memories → retrieval latency < 100ms
  ├── [ ] D2. Test: duplicate fact → confidence boost, no new record
  ├── [ ] D3. Test: session restart → no re-extraction of same facts
  └── [ ] D4. Test: index persists across restarts
```

## Key Files

- `app/app.py` — main entry, memory wiring, session startup
- `app/memory/index_store.py` — **NEW** ANN index (cKDTree, joblib persistence)
- `app/memory/retrieval.py` — **REWRITTEN** ANN-powered retrieval
- `app/memory/extractor.py` — episodic + semantic extraction
- `app/memory/review.py` — FSRS decay
- `app/memory/segmenter.py` — conversation segmentation
- `app/database.py` — SQLite access layer
