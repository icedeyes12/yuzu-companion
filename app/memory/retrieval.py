# FILE: retrieval.py
# DESCRIPTION: Memory retrieval pipeline - cosine similarity + hybrid scoring

import math
import functools
from datetime import datetime, timedelta
from app.database import (
    get_db_session, SemanticMemory, EpisodicMemory, ConversationSegment, Message
)
from app.memory.embedder import blob_to_vec
from app.memory.index_store import get_index_store


# ── Temporal cue helpers (inlined from deleted tools/memory_search.py) ─────────

_TEMPORAL_CUES = [
    "kemarin", "minggu lalu", "waktu itu", "terakhir", "pas aku",
    "last time", "yesterday", "last week", "before", "remember when",
    "dulu", "tadi", "bulan lalu", "tahun lalu", "pernah",
    "last month", "last year", "earlier", "previously", "ago"
]

_MONTH_NAMES = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
    "january": 1, "february": 2, "march": 3, "may": 5,
    "june": 6, "july": 7, "august": 8, "october": 10, "december": 12,
}

_RELATIVE_CUES = {
    "kemarin":     lambda now: (now - timedelta(days=1), now),
    "yesterday":   lambda now: (now - timedelta(days=1), now),
    "tadi":        lambda now: (now.replace(hour=0, minute=0, second=0), now),
    "minggu lalu": lambda now: (now - timedelta(weeks=1), now),
    "last week":   lambda now: (now - timedelta(weeks=1), now),
    "bulan lalu":  lambda now: (now - timedelta(days=30), now),
    "last month":  lambda now: (now - timedelta(days=30), now),
    "tahun lalu":  lambda now: (now - timedelta(days=365), now),
    "last year":   lambda now: (now - timedelta(days=365), now),
}


def _detect_month(query):
    ql = query.lower()
    for name, num in _MONTH_NAMES.items():
        if name in ql:
            return num
    return None


def _detect_time_window(query):
    now = datetime.now()
    ql = query.lower()
    month = _detect_month(query)
    if month is not None:
        year = now.year if month <= now.month else now.year - 1
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        return start, end
    for cue, calc in _RELATIVE_CUES.items():
        if cue in ql:
            return calc(now)
    return None


def _search_temporal_messages(session_id, start, end, limit=200):
    results = []
    try:
        start_str = start.strftime('%Y-%m-%d %H:%M:%S')
        end_str = end.strftime('%Y-%m-%d %H:%M:%S')
        with get_db_session() as session:
            messages = (
                session.query(Message)
                .filter(
                    Message.session_id == session_id,
                    Message.role.in_(['user', 'assistant']),
                    Message.timestamp >= start_str,
                    Message.timestamp <= end_str,
                )
                .order_by(Message.timestamp.asc())
                .limit(limit)
                .all()
            )
            for msg in messages:
                content = msg.content
                if msg.content_encrypted:
                    try:
                        from app.encryption import encryptor
                        content = encryptor.decrypt(content)
                    except (KeyError, ValueError, RuntimeError):
                        content = "[ENCRYPTED]"
                results.append({
                    "timestamp": msg.timestamp,
                    "role": msg.role,
                    "content": content[:500],
                })
    except (KeyError, AttributeError, RuntimeError) as e:
        print(f"[retrieval] Temporal scan failed: {e}")
    return results


# ── Original retrieval functions ─────────────────────────────────────────────

def _recency_factor(last_accessed) -> float:
    """Recency score 0.0–1.0, half-life of 24 hours."""
    if not last_accessed:
        return 0.1
    now = datetime.now()
    if isinstance(last_accessed, str):
        try:
            last_accessed = datetime.strptime(last_accessed, '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return 0.1
    delta_hours = (now - last_accessed).total_seconds() / 3600.0
    return math.exp(-delta_hours / 24.0)


@functools.lru_cache(maxsize=1024)
def _embed_query(text: str) -> list[float] | None:
    """Embed a query string via Chutes API."""
    try:
        from app.memory.embedder import embed_text
        return embed_text(text)
    except Exception as e:
        print(f"[WARNING] Query embedding failed: {e}")
        return None


def retrieve_semantic_memories(session_id, query=None, limit=15):
    """
    Retrieve semantic memories by cosine similarity to query.

    If query is provided: embed query, run ANN search via cKDTree index,
      then re-rank top candidates with hybrid scoring.
    If query is None or embedding fails: fall back to importance × confidence
      with a targeted DB query (avoids full table scan).
    """
    # ── Fast path: ANN search via cKDTree index ───────────────────────────────
    query_vec = _embed_query(query) if query else None
    ann_results: list[tuple[int, float]] = []
    ann_used = False
    if query_vec is not None:
        try:
            import numpy as np
            store = get_index_store(session_id)
            ann_results = store.search_semantic(np.array(query_vec, dtype=np.float32), k=limit * 3)
            ann_used = True
        except (ImportError, OSError, ValueError, RuntimeError) as e:
            print(f"[WARNING] ANN semantic search failed (index corrupt or missing), falling back to DB: {e}")
        except Exception as e:
            print(f"[WARNING] ANN semantic search failed unexpectedly, falling back to DB: {type(e).__name__}: {e}")

    with get_db_session() as session:
        if ann_results:
            # Fetch full records for ANN candidates, then re-rank with hybrid score
            ann_ids = [rid for rid, _ in ann_results]
            memories = session.query(SemanticMemory).filter(
                SemanticMemory.id.in_(ann_ids)
            ).all()
            id_to_mem = {m.id: m for m in memories}
            scored = []
            for rid, cosine_dist in ann_results:
                mem = id_to_mem.get(rid)
                if mem is None:
                    continue
                cosine_sim = 1.0 - cosine_dist
                cosine_sim = max(0.0, min(1.0, cosine_sim))  # clamp to [0, 1]
                try:
                    mem_vec = blob_to_vec(mem.embedding_vector)
                    if not query_vec:
                        raise ValueError("no query_vec")
                    dot = sum(a * b for a, b in zip(query_vec, mem_vec))
                    norm_q = math.sqrt(sum(x * x for x in query_vec))
                    norm_m = math.sqrt(sum(x * x for x in mem_vec))
                    if norm_q and norm_m:
                        true_sim = max(0.0, min(1.0, dot / (norm_q * norm_m)))
                    else:
                        true_sim = cosine_sim
                except (ValueError, TypeError, RuntimeError):
                    true_sim = cosine_sim
                score = true_sim * 0.6 + (mem.importance or 0.5) * 0.2 + (mem.confidence or 0.5) * 0.2
                score = max(0.0, min(1.0, score))  # clamp final score
                scored.append({
                    'id': mem.id,
                    'entity': mem.entity,
                    'relation': mem.relation,
                    'target': mem.target,
                    'confidence': mem.confidence,
                    'importance': mem.importance,
                    'score': score,
                    'ann': ann_used,
                })
            scored.sort(key=lambda x: x['score'], reverse=True)
            top_ids = [m['id'] for m in scored[:limit]]
            if top_ids:
                for mem in session.query(SemanticMemory).filter(
                    SemanticMemory.id.in_(top_ids)
                ).all():
                    mem.access_count = (mem.access_count or 0) + 1
                    mem.last_accessed = datetime.now()
                session.commit()
            return scored[:limit]

        # ── Fallback: no query or embedding failed — importance × confidence ─
        memories = session.query(SemanticMemory).filter(
            SemanticMemory.session_id == session_id
        ).order_by(
            (SemanticMemory.importance * SemanticMemory.confidence).desc()
        ).limit(limit).all()
        scored = [{
            'id': m.id, 'entity': m.entity, 'relation': m.relation, 'target': m.target,
            'confidence': m.confidence, 'importance': m.importance,
            'score': max(0.0, min(1.0, (m.importance or 0.5) * (m.confidence or 0.5))),
            'ann': False,
        } for m in memories]
        return scored


def retrieve_episodic_memories(session_id, query=None, limit=5):
    """
    Retrieve episodic memories by cosine similarity + hybrid score.

    Score = cosine_sim * 0.5 + importance * 0.25 + recency * 0.25
    """
    import numpy as np
    query_vec = _embed_query(query) if query else None
    ann_results: list[tuple[int, float]] = []
    ann_used = False
    if query_vec is not None:
        try:
            store = get_index_store(session_id)
            ann_results = store.search_episodic(np.array(query_vec, dtype=np.float32), k=limit * 3)
            ann_used = True
        except (ImportError, OSError, ValueError, RuntimeError) as e:
            print(f"[WARNING] ANN episodic search failed (index corrupt/missing), falling back: {e}")
        except Exception as e:
            print(f"[WARNING] ANN episodic search failed unexpectedly, falling back: {type(e).__name__}: {e}")

    with get_db_session() as session:
        if ann_results:
            ann_ids = [rid for rid, _ in ann_results]
            memories = session.query(EpisodicMemory).filter(
                EpisodicMemory.id.in_(ann_ids)
            ).all()
            id_to_mem = {m.id: m for m in memories}
            scored = []
            for rid, cosine_dist in ann_results:
                mem = id_to_mem.get(rid)
                if mem is None:
                    continue
                cosine_sim = 1.0 - cosine_dist
                cosine_sim = max(0.0, min(1.0, cosine_sim))
                recency = _recency_factor(mem.last_accessed)
                try:
                    mem_vec = blob_to_vec(mem.embedding)
                    if query_vec:
                        dot = sum(a * b for a, b in zip(query_vec, mem_vec))
                        norm_q = math.sqrt(sum(x * x for x in query_vec))
                        norm_m = math.sqrt(sum(x * x for x in mem_vec))
                        true_sim = max(0.0, min(1.0, dot / (norm_q * norm_m))) if (norm_q and norm_m) else cosine_sim
                    else:
                        true_sim = cosine_sim
                except Exception:
                    true_sim = cosine_sim
                score = true_sim * 0.5 + (mem.importance or 0.5) * 0.25 + recency * 0.25
                score = max(0.0, min(1.0, score))
                scored.append({
                    'id': mem.id, 'summary': mem.summary,
                    'importance': mem.importance, 'emotional_weight': mem.emotional_weight,
                    'score': score,
                    'ann': ann_used,
                })
            scored.sort(key=lambda x: x['score'], reverse=True)
            top_ids = [m['id'] for m in scored[:limit]]
            if top_ids:
                for mem in session.query(EpisodicMemory).filter(
                    EpisodicMemory.id.in_(top_ids)
                ).all():
                    mem.access_count = (mem.access_count or 0) + 1
                    mem.last_accessed = datetime.now()
                session.commit()
            return scored[:limit]

        # ── Fallback: importance + recency sort ──────────────────────────────
        memories = session.query(EpisodicMemory).filter(
            EpisodicMemory.session_id == session_id
        ).all()
        if not memories:
            return []
        scored = []
        for mem in memories:
            recency = _recency_factor(mem.last_accessed)
            score = ((mem.importance or 0.5) + (mem.emotional_weight or 0.0) * 0.5 + recency)
            score = max(0.0, min(1.0, score))
            scored.append({
                'id': mem.id, 'summary': mem.summary,
                'importance': mem.importance, 'emotional_weight': mem.emotional_weight,
                'score': score,
                'ann': False,
            })
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored[:limit]


def retrieve_segments(session_id, query=None, limit=5):
    """Retrieve conversation segments by ANN similarity or recency."""
    import numpy as np
    query_vec = _embed_query(query) if query else None
    ann_results: list[tuple[int, float]] = []
    ann_used = False
    if query_vec is not None:
        try:
            store = get_index_store(session_id)
            ann_results = store.search_segments(np.array(query_vec, dtype=np.float32), k=limit * 3)
            ann_used = True
        except (ImportError, OSError, ValueError, RuntimeError) as e:
            print(f"[WARNING] ANN segment search failed (index corrupt/missing), falling back: {e}")
        except Exception as e:
            print(f"[WARNING] ANN segment search failed unexpectedly, falling back: {type(e).__name__}: {e}")

    with get_db_session() as session:
        if ann_results:
            ann_ids = [rid for rid, _ in ann_results]
            segments = session.query(ConversationSegment).filter(
                ConversationSegment.id.in_(ann_ids)
            ).all()
            id_to_seg = {s.id: s for s in segments}
            scored = []
            for rid, cosine_dist in ann_results:
                seg = id_to_seg.get(rid)
                if seg is None:
                    continue
                cosine_sim = 1.0 - cosine_dist
                cosine_sim = max(0.0, min(1.0, cosine_sim))
                score = cosine_sim * 0.5 + (seg.importance or 0.5) * 0.5
                score = max(0.0, min(1.0, score))
                scored.append({
                    'id': seg.id, 'summary': seg.summary, 'importance': seg.importance,
                    'start_message_id': seg.start_message_id, 'end_message_id': seg.end_message_id,
                    'score': score,
                    'ann': ann_used,
                })
            scored.sort(key=lambda x: x['score'], reverse=True)
            return scored[:limit]

        # ── Fallback: recency sort ───────────────────────────────────────────
        segments = session.query(ConversationSegment).filter(
            ConversationSegment.session_id == session_id
        ).order_by(ConversationSegment.created_at.desc()).limit(limit).all()
        return [{
            'id': s.id, 'summary': s.summary, 'importance': s.importance,
            'start_message_id': s.start_message_id, 'end_message_id': s.end_message_id,
            'score': max(0.0, min(1.0, s.importance or 0.5)),
            'ann': False,
        } for s in segments]


def retrieve_memory(session_id, query=None):
    """
    Main retrieval entry point.
    
    Args:
        session_id: current session
        query: optional user query for semantic search
    
    Returns:
        dict with semantic, episodic, segments
    """
    try:
        semantic = retrieve_semantic_memories(session_id, query=query, limit=15)
    except Exception as e:
        print(f"[WARNING] Semantic memory retrieval failed: {e}")
        semantic = []

    try:
        episodic = retrieve_episodic_memories(session_id, query=query, limit=5)
    except Exception as e:
        print(f"[WARNING] Episodic memory retrieval failed: {e}")
        episodic = []

    try:
        segments = retrieve_segments(session_id, query=query, limit=5)
    except Exception as e:
        print(f"[WARNING] Segment retrieval failed: {e}")
        segments = []

    # Supplement: if query contains temporal cues, also scan messages directly
    temporal_messages = []
    if query:
        try:
            time_window = _detect_time_window(query)
            if time_window:
                start, end = time_window
                temporal_messages = _search_temporal_messages(session_id, start, end)
        except Exception:
            pass

    return {
        'semantic': semantic,
        'episodic': episodic,
        'segments': segments,
        'temporal_messages': temporal_messages,
    }


def format_memory(memory_bundle):
    """Format a memory bundle into a text string for system message injection."""
    parts = []

    semantic = memory_bundle.get('semantic', [])
    if semantic:
        parts.append("Known preferences:")
        for mem in semantic:
            parts.append(f"- {mem['entity']} {mem['relation']} {mem['target']}")

    episodic = memory_bundle.get('episodic', [])
    if episodic:
        parts.append("\nRecent important events:")
        for mem in episodic:
            summary = mem.get('summary', '')
            if len(summary) > 200:
                summary = summary[:200] + '...'
            parts.append(f"- {summary}")

    segments = memory_bundle.get('segments', [])
    if segments:
        parts.append("\nRelevant past context:")
        for seg in segments:
            summary = seg.get('summary', '')
            if len(summary) > 200:
                summary = summary[:200] + '...'
            parts.append(f"- {summary}")

    temporal = memory_bundle.get('temporal_messages', [])
    if temporal:
        parts.append("\nMessages from requested time period:")
        for msg in temporal[:10]:
            ts = msg.get('timestamp', '')[:16]
            role = msg.get('role', '')
            content = msg.get('content', '')[:300]
            parts.append(f"- [{ts}] {role}: {content}")

    return '\n'.join(parts)
