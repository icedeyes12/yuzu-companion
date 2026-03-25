# [FILE: memory/index_store.py]
# [DESCRIPTION: ANN index per session using scipy cKDTree (cosine metric),
#               persisted to disk via joblib pickle]

import atexit
import os
import numpy as np
import joblib
from scipy.spatial import cKDTree

from app.database import get_db_session, SemanticMemory, EpisodicMemory, ConversationSegment
from app.memory.embedder import blob_to_vec, get_embed_dim

_INDEX_DIR = os.path.join(os.path.dirname(__file__), 'nn_indexes')
_INDEX_VERSION = 4  # schema version — bump to force rebuild on breaking changes

# ── Directory setup ────────────────────────────────────────────────────────────

def _index_path(session_id: int, label: str) -> str:
    os.makedirs(_INDEX_DIR, exist_ok=True)
    return os.path.join(_INDEX_DIR, f"session_{session_id}_{label}.pkl")

# ── Index wrapper ───────────────────────────────────────────────────────────────

class NNIndex:
    """
    Wraps scipy cKDTree for cosine-approximate nearest-neighbor search.

    Because cKDTree only supports euclidean distance, we L2-normalize all
    vectors before inserting/querying — this makes euclidean distance on
    normalized vectors equivalent to cosine distance.
    """

    def __init__(self, ids: list[int], vecs: np.ndarray):
        # vecs shape: (N, 4096), float32
        norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-8
        self._normed = (vecs / norms).astype(np.float32)
        self._ids = list(ids)
        self._tree = cKDTree(self._normed)
        self._embed_dim = get_embed_dim()  # store actual dim for validation

    def search(self, query_vec: np.ndarray, k: int) -> list[tuple[int, float]]:
        """Returns [(id, distance), ...] closest to query_vec (cosine distance)."""
        if self._normed.shape[0] == 0 or k <= 0:
            return []
        norm = np.linalg.norm(query_vec) + 1e-8
        q = (np.asarray(query_vec, dtype=np.float32) / norm).reshape(1, -1)
        k = min(k, self._normed.shape[0])
        distances, indices = self._tree.query(q, k=k)
        return [(self._ids[i], float(distances[0][j])) for j, i in enumerate(indices[0])]

    @property
    def size(self) -> int:
        return self._normed.shape[0]

    @property
    def embed_dim(self) -> int:
        """Return embedding dimension this index was built with."""
        return self._embed_dim

    def save(self, path: str):
        IndexStore._atomic_save((_INDEX_VERSION, self._embed_dim, self._ids, self._normed), path)

    @classmethod
    def load(cls, path: str) -> "NNIndex":
        data = joblib.load(path)
        # New format v2+: (version, embed_dim, ids, normed)
        if isinstance(data, tuple) and len(data) >= 3:
            version = data[0]
            if version == _INDEX_VERSION and len(data) == 4:
                _, embed_dim, ids, normed = data
                idx = cls(ids, normed)
                idx._embed_dim = embed_dim
                return idx
            elif version == 1 and len(data) == 3:
                # Old format (version, ids, normed): assume 4096, force rebuild via ValueError
                pass
        raise ValueError(f"Stale or corrupted index format at {path}")

    @classmethod
    def build(cls, ids: list[int], vecs: np.ndarray, embed_dim: int | None = None) -> "NNIndex":
        idx = cls(ids, vecs)
        if embed_dim is not None:
            idx._embed_dim = embed_dim
        return idx


# ── Per-session store ──────────────────────────────────────────────────────────

class IndexStore:
    """
    Manages ANN indexes for one session across three memory types:
      semantic   — SemanticMemory.embedding_vector
      episodic   — EpisodicMemory.embedding
      segments   — ConversationSegment.embedding

    Indexes are:
    - Loaded lazily on first search
    - Rebuilt from DB when missing, stale, or on explicit rebuild()
    - Persisted to disk as joblib pickles (atomic write)
    - Invalidated in-memory when new memories are written (fixes staleness)
    """

    def __init__(self, session_id: int):
        self.session_id = session_id
        self._semantic: NNIndex | None = None
        self._episodic: NNIndex | None = None
        self._segments: NNIndex | None = None
        self._semantic_loaded = False
        self._episodic_loaded = False
        self._segments_loaded = False
        self._ann_errors: list[str] = []  # session-scoped error log

    def _record_error(self, index_name: str, op: str, exc: Exception):
        """Append a formatted error entry to the session error log."""
        self._ann_errors.append(f"[{index_name}] {op} failed: {type(exc).__name__}: {exc}")

    def get_ann_errors(self) -> list[str]:
        """Return copy of ANN errors seen for this session."""
        return list(self._ann_errors)

    def clear_ann_errors(self):
        """Clear the ANN error log (e.g., after successful recovery)."""
        self._ann_errors.clear()

    # ── Atomic save ────────────────────────────────────────────────────────────

    @staticmethod
    def _atomic_save(data, path: str):
        """Write to temp file then atomic-rename to prevent corrupted pickles."""
        tmp = path + ".tmp"
        joblib.dump(data, tmp, compress=3)
        os.replace(tmp, path)

    # ── Lazy load / build ──────────────────────────────────────────────────────

    def _ensure_semantic(self):
        if self._semantic_loaded:
            return
        path = _index_path(self.session_id, "semantic")
        if os.path.exists(path):
            try:
                self._semantic = NNIndex.load(path)
                self._semantic_loaded = True
                return
            except Exception as e:
                self._record_error("semantic", "load", e)
                pass  # fall through to rebuild
        self._semantic = self._rebuild_semantic()
        self._semantic_loaded = True

    def _ensure_episodic(self):
        if self._episodic_loaded:
            return
        path = _index_path(self.session_id, "episodic")
        if os.path.exists(path):
            try:
                self._episodic = NNIndex.load(path)
                self._episodic_loaded = True
                return
            except Exception as e:
                self._record_error("episodic", "load", e)
                pass  # fall through to rebuild
        self._episodic = self._rebuild_episodic()
        self._episodic_loaded = True

    def _ensure_segments(self):
        if self._segments_loaded:
            return
        path = _index_path(self.session_id, "segments")
        if os.path.exists(path):
            try:
                self._segments = NNIndex.load(path)
                self._segments_loaded = True
                return
            except Exception as e:
                self._record_error("segments", "load", e)
                pass  # fall through to rebuild
        self._segments = self._rebuild_segments()
        self._segments_loaded = True

    # ── Rebuild from DB ────────────────────────────────────────────────────────

    def _rebuild_semantic(self) -> NNIndex | None:
        with get_db_session() as session:
            rows = session.query(SemanticMemory.id, SemanticMemory.embedding_vector).filter(
                SemanticMemory.session_id == self.session_id,
                SemanticMemory.embedding_vector.isnot(None),
            ).all()
        if not rows:
            return None
        ids = []
        vecs = []
        for r in rows:
            vec = blob_to_vec(r.embedding_vector)
            if len(vec) == 0:
                continue  # skip zero vectors (from failed embed_text calls)
            ids.append(r.id)
            vecs.append(self._pad_or_truncate(vec))
        if not ids:
            return None
        vecs_arr = np.array(vecs, dtype=np.float32)
        idx = NNIndex.build(ids, vecs_arr)
        idx.save(_index_path(self.session_id, "semantic"))
        return idx

    def _rebuild_episodic(self) -> NNIndex | None:
        with get_db_session() as session:
            rows = session.query(EpisodicMemory.id, EpisodicMemory.embedding).filter(
                EpisodicMemory.session_id == self.session_id,
                EpisodicMemory.embedding.isnot(None),
            ).all()
        if not rows:
            return None
        ids = []
        vecs = []
        for r in rows:
            vec = blob_to_vec(r.embedding)
            if len(vec) == 0:
                continue
            ids.append(r.id)
            vecs.append(self._pad_or_truncate(vec))
        if not ids:
            return None
        vecs_arr = np.array(vecs, dtype=np.float32)
        idx = NNIndex.build(ids, vecs_arr)
        idx.save(_index_path(self.session_id, "episodic"))
        return idx

    def _rebuild_segments(self) -> NNIndex | None:
        with get_db_session() as session:
            rows = session.query(ConversationSegment.id, ConversationSegment.embedding).filter(
                ConversationSegment.session_id == self.session_id,
                ConversationSegment.embedding.isnot(None),
            ).all()
        if not rows:
            return None
        ids = []
        vecs = []
        for r in rows:
            vec = blob_to_vec(r.embedding)
            if len(vec) == 0:
                continue
            ids.append(r.id)
            vecs.append(self._pad_or_truncate(vec))
        if not ids:
            return None
        vecs_arr = np.array(vecs, dtype=np.float32)
        idx = NNIndex.build(ids, vecs_arr)
        idx.save(_index_path(self.session_id, "segments"))
        return idx

    @staticmethod
    def _pad_or_truncate(vec: list[float]) -> list[float]:
        """Normalize embedding dimension to _EMBED_DIM, logging mismatches."""
        embed_dim = get_embed_dim()
        if len(vec) == embed_dim:
            return vec
        if len(vec) == 0:
            print("[WARNING] Empty embedding vector encountered, using zeros")
            return [0.0] * embed_dim
        if len(vec) < embed_dim:
            print(f"[WARNING] Embedding dim {len(vec)} < {embed_dim}, padding with zeros")
            return vec + [0.0] * (embed_dim - len(vec))
        print(f"[WARNING] Embedding dim {len(vec)} > {embed_dim}, truncating")
        return vec[:embed_dim]

    # ── Invalidate (mark dirty) ─────────────────────────────────────────────────

    def _invalidate_semantic(self):
        self._semantic = None
        self._semantic_loaded = False

    def _invalidate_episodic(self):
        self._episodic = None
        self._episodic_loaded = False

    def _invalidate_segments(self):
        self._segments = None
        self._segments_loaded = False

    # ── Incremental add (preferred over full rebuild) ─────────────────────────

    def add_semantic(self, mem_id: int, vec: np.ndarray):
        """Incrementally add a new semantic memory to the live index."""
        self._ensure_semantic()
        if self._semantic is None:
            self._invalidate_semantic()
            self._ensure_semantic()
            if self._semantic is None:
                return
        ids = self._semantic._ids[:]
        vecs = self._semantic._normed[:]
        new_norm = (vec / (np.linalg.norm(vec) + 1e-8)).astype(np.float32)
        if mem_id not in ids:
            ids.append(mem_id)
            vecs = np.vstack([vecs, new_norm])
            self._semantic = NNIndex.build(ids, vecs)
            self._semantic.save(_index_path(self.session_id, "semantic"))

    def add_episodic(self, mem_id: int, vec: np.ndarray):
        """Incrementally add a new episodic memory to the live index."""
        self._ensure_episodic()
        if self._episodic is None:
            self._invalidate_episodic()
            self._ensure_episodic()
            if self._episodic is None:
                return
        ids = self._episodic._ids[:]
        vecs = self._episodic._normed[:]
        new_norm = (vec / (np.linalg.norm(vec) + 1e-8)).astype(np.float32)
        if mem_id not in ids:
            ids.append(mem_id)
            vecs = np.vstack([vecs, new_norm])
            self._episodic = NNIndex.build(ids, vecs)
            self._episodic.save(_index_path(self.session_id, "episodic"))

    def add_segment(self, seg_id: int, vec: np.ndarray):
        """Incrementally add a new segment to the live index."""
        self._ensure_segments()
        if self._segments is None:
            self._invalidate_segments()
            self._ensure_segments()
            if self._segments is None:
                return
        ids = self._segments._ids[:]
        vecs = self._segments._normed[:]
        new_norm = (vec / (np.linalg.norm(vec) + 1e-8)).astype(np.float32)
        if seg_id not in ids:
            ids.append(seg_id)
            vecs = np.vstack([vecs, new_norm])
            self._segments = NNIndex.build(ids, vecs)
            self._segments.save(_index_path(self.session_id, "segments"))

    # ── Public search API ───────────────────────────────────────────────────────

    def search_semantic(self, query_vec: np.ndarray, k: int = 15) -> list[tuple[int, float]]:
        self._ensure_semantic()
        if self._semantic is None:
            return []
        return self._semantic.search(query_vec, k)

    def search_episodic(self, query_vec: np.ndarray, k: int = 5) -> list[tuple[int, float]]:
        self._ensure_episodic()
        if self._episodic is None:
            return []
        return self._episodic.search(query_vec, k)

    def search_segments(self, query_vec: np.ndarray, k: int = 5) -> list[tuple[int, float]]:
        self._ensure_segments()
        if self._segments is None:
            return []
        return self._segments.search(query_vec, k)

    # ── Rebuild ─────────────────────────────────────────────────────────────────

    def rebuild(self):
        self._semantic = self._rebuild_semantic()
        self._episodic = self._rebuild_episodic()
        self._segments = self._rebuild_segments()
        self._semantic_loaded = True
        self._episodic_loaded = True
        self._segments_loaded = True

    # ── Close ───────────────────────────────────────────────────────────────────

    def close(self):
        self._semantic = None
        self._episodic = None
        self._segments = None
        self._semantic_loaded = False
        self._episodic_loaded = False
        self._segments_loaded = False


# ── Process-global cache ────────────────────────────────────────────────────────

_index_cache: dict[int, IndexStore] = {}

def get_index_store(session_id: int) -> IndexStore:
    if session_id not in _index_cache:
        _index_cache[session_id] = IndexStore(session_id)
    return _index_cache[session_id]

def close_index_store(session_id: int):
    if session_id in _index_cache:
        _index_cache[session_id].close()
        del _index_cache[session_id]

def close_all_index_stores():
    """Close all cached stores and clear the cache. Called on process exit."""
    for store in list(_index_cache.values()):
        store.close()
    _index_cache.clear()

# Ensure all index stores are closed on interpreter shutdown
atexit.register(close_all_index_stores)