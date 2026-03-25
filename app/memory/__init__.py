# Memory system public API for Yuzu Companion
#
# Single import point for all memory operations.
# External code (app.py, tools, etc.) should import from here, not from internals.
#
# Legacy note: the extraction/retrieval pipeline is fully independent from the
# legacy global_knowledge_json system. Both can run in parallel.

from app.memory.extractor import (
    process_messages_for_memory,
    extract_semantic_facts,
    upsert_semantic_memory,
    create_episodic_memory,
)
from app.memory.retrieval import (
    retrieve_memory,
    retrieve_semantic_memories,
    retrieve_episodic_memories,
    retrieve_segments,
    format_memory,
)
from app.memory.review import (
    run_decay,
    decay_semantic_memories,
    decay_episodic_memories,
    reinforce_memory,
)
from app.memory.segmenter import (
    segment_session,
)
from app.memory.index_store import (
    get_index_store,
    close_index_store,
)

__all__ = [
    "process_messages_for_memory",
    "extract_semantic_facts",
    "upsert_semantic_memory",
    "create_episodic_memory",
    "retrieve_memory",
    "retrieve_semantic_memories",
    "retrieve_episodic_memories",
    "retrieve_segments",
    "format_memory",
    "run_decay",
    "decay_semantic_memories",
    "decay_episodic_memories",
    "reinforce_memory",
    "segment_session",
    "get_index_store",
    "close_index_store",
    "extract_memories",
    "retrieve_memories",
    "get_memory_stats",
]

# ── Aliases for cleaner public API ──────────────────────────────────────────

extract_memories = process_messages_for_memory
retrieve_memories = retrieve_memory


# ── Stats helper ─────────────────────────────────────────────────────────────

def get_memory_stats(session_id: int) -> dict:
    """
    Return a snapshot of memory system state for a session.

    Returns:
        dict with keys:
            semantic_count     — rows in semantic_memories
            episodic_count      — rows in episodic_memories
            segment_count       — rows in conversation_segments
            index_semantic_size — vectors in ANN semantic index (0 if not loaded)
            index_episodic_size  — vectors in ANN episodic index
            index_segments_size  — vectors in ANN segments index
            ann_errors          — index load/rebuild errors seen this session (from index_store)
            last_decay          — ISO timestamp of last decay run, or None
            legacy_memory_keys  — number of keys in session memory_json
    """
    from app.database import Database
    from app.database import ConversationSegment
    from app.database import EpisodicMemory
    from app.database import SemanticMemory
    from app.database import get_db_session
    from app.memory.review import _get_last_decay_time

    try:
        with get_db_session() as session:
            semantic_count = session.query(SemanticMemory).filter(
                SemanticMemory.session_id == session_id
            ).count()
            episodic_count = session.query(EpisodicMemory).filter(
                EpisodicMemory.session_id == session_id
            ).count()
            segment_count = session.query(ConversationSegment).filter(
                ConversationSegment.session_id == session_id
            ).count()
    except Exception:
        semantic_count = episodic_count = segment_count = -1

    # Index sizes — read from disk files without loading into memory (avoids
    # expensive DB query + vector rebuild that _ensure_* would trigger)
    try:
        from app.memory.index_store import _index_path
        import os
        sp = _index_path(session_id, "semantic")
        ep = _index_path(session_id, "episodic")
        tp = _index_path(session_id, "segments")
        index_semantic_size = os.path.getsize(sp) // (4 * 4096 + 8) if os.path.exists(sp) else 0
        index_episodic_size = os.path.getsize(ep) // (4 * 4096 + 8) if os.path.exists(ep) else 0
        index_segments_size = os.path.getsize(tp) // (4 * 4096 + 8) if os.path.exists(tp) else 0
        ann_errors: list[str] = []
    except Exception:
        index_semantic_size = index_episodic_size = index_segments_size = -1
        ann_errors = []

    last_decay = _get_last_decay_time()

    try:
        session_mem = Database.get_session_memory(session_id)
        legacy_memory_keys = len(session_mem) if session_mem else 0
    except Exception:
        legacy_memory_keys = -1

    extraction_errors = 0
    try:
        from app.memory.extractor import get_extraction_error_count
        extraction_errors = get_extraction_error_count()
    except Exception:
        pass

    return {
        "semantic_count": semantic_count,
        "episodic_count": episodic_count,
        "segment_count": segment_count,
        "index_semantic_size": index_semantic_size,
        "index_episodic_size": index_episodic_size,
        "index_segments_size": index_segments_size,
        "ann_errors": ann_errors,
        "extraction_errors": extraction_errors,
        "last_decay": last_decay,
        "legacy_memory_keys": legacy_memory_keys,
    }
