# Changelog

All notable changes to this project will be documented in this file.

---

## [1.0.70.1] — 2026-03-25

### Fixed

- **Header audit**: Standardized all file headers to `FILE:` / `DESCRIPTION:` format across 52 files (.py, .css, .js, .html). Removed legacy multi-line comment blocks (version banners, author tags, timestamps). Correct comment syntax per file type.

---

## [1.0.70] — 2026-03-25

### Added

- **Memory system v1 — full implementation**
  - `memory/embedder.py`: Chutes API client for `Qwen/Qwen3-Embedding-8B` embeddings. `embed_text()`, `embed_texts()`, `cosine_similarity()`, `vec_to_blob()`, `blob_to_vec()`.
  - `memory/extractor.py`: Semantic triple extraction (regex + LLM fallback), episodic summary generation (LLM + truncation fallback), emotional weight scoring, duplicate fact deduplication via embedding similarity.
  - `memory/segmenter.py`: Conversation window segmentation by time gap (15 min) and size (20 msgs). Minimum 5 messages per segment.
  - `memory/retrieval.py`: ANN retrieval via cKDTree + hybrid re-ranking. Supports temporal cue queries (Indonesian + English). Three-layer retrieval: semantic (top 15), episodic (top 5), segments (top 5).
  - `memory/review.py`: FSRS-inspired decay with 6-hour cooldown. Semantic stability: `max(24h × (1 + access_count × 0.5), 24h)`. Episodic stability: `max(48h × (1 + access_count × 0.3), 48h)`. Reinforcement: `importance += 0.05` on retrieval.
  - `memory/index_store.py`: Per-session ANN indexes using scipy cKDTree. Lazy loading, incremental add, atomic joblib persistence. Versioned format (v2) with auto-rebuild on corruption.
  - `memory/models.py`: Re-exports `SemanticMemory`, `EpisodicMemory`, `ConversationSegment`.
  - `memory/docs/`: Full documentation — architecture, retrieval, segmentation, FSRS model, semantic memory design.
  - `database.py`: Three new tables — `semantic_memories`, `episodic_memories`, `conversation_segments`. Full indexing on `session_id`, `importance`, `confidence`.
  - `tools/memory_store.py`: Tool backing `MCP_MEMORY_STORE` for programmatic memory writes.
- **Embedding model** for semantic memory search
- **Preview button** for HTML codeblocks
- **Docker** installation support (`Dockerfile`, `docker-compose.yml`)
- **`app/README.md`**: Comprehensive app-layer reference with mermaid diagrams

### Changed

- `memory/index_store.py`: Migrated from in-memory-only to persistent joblib pickles with atomic writes
- `memory/extractor.py`: Incremental ANN index updates via `IndexStore.add_*()` instead of full rebuilds
- `memory/retrieval.py`: LRU-cached query embeddings (`lru_cache(maxsize=1024)`), true cosine similarity recomputation after ANN retrieval, graceful fallbacks at every layer
- Semantic triple deduplication: now uses embedding similarity (≥0.95) to merge near-duplicate facts before insert

### Fixed

- **ANN index staleness**: New memories now update the live index immediately instead of requiring a full rebuild
- **Decay state persistence**: `.decay_state.json` now correctly tracks last run across process restarts
- **Empty embedding handling**: `_pad_or_truncate()` handles zero-length vectors gracefully
- **Embedding dimension validation**: `NNIndex` now stores actual embedding dimension and validates on load; stale v1 indexes raise `ValueError` and trigger rebuild

---

## [1.0.69.28v4] — 2026-03-24

### Added
- Embedding model for semantic memory search
- Preview button for HTML codeblocks
- Docker installation support (Dockerfile, docker-compose.yml)

### Fixed
- Various bug fixes
