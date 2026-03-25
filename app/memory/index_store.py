# [FILE: memory/index_store.py]
# [DESCRIPTION: ANN index per session using scipy cKDTree (cosine metric),
#               persisted to disk via joblib pickle]

import os
import numpy as np
import joblib
from scipy.spatial import cKDTree

from app.database import get_db_session, SemanticMemory, EpisodicMemory, ConversationSegment
from app.memory.embedder import blob_to_vec

_INDEX_DIR = os.path.join(os.path.dirname(__file__), 'nn_indexes')
_EMBED_DIM = 4096  # Qwen3-Embedding-8B

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

    def save(self, path: str):
        joblib.dump((self._ids, self._normed), path, compress=3)

    @classmethod
    def load(cls, path: str) -> "NNIndex":
        ids, normed = joblib.load(path)
        return cls(ids, normed)

    @classmethod
    def build(cls, ids: list[int], vecs: np.ndarray) -> "NNIndex":
        return cls(ids, vecs)


# ── Per-session store ──────────────────────────────────────────────────────────

class IndexStore:
    """
    Manages ANN indexes for one session across three memory types:
      semantic   — SemanticMemory.embedding_vector
      episodic   — EpisodicMemory.embedding
      segments   — ConversationSegment.embedding

    Indexes are:
    - Loaded lazily on first search
    - Rebuilt from DB when missing or on explicit rebuild()
    - Persisted to disk as joblib pickles
    """

    def __init__(self, session_id: int):
        self.session_id = session_id
        self._semantic: NNIndex | None = None
        self._episodic: NNIndex | None = None
        self._segments: NNIndex | None = None
        self._semantic_loaded = False
        self._episodic_loaded = False
        self._segments_loaded = False

    # ── Lazy load / build ─────────────────────────────────────────────────────

    def _ensure_semantic(self):
        if self._semantic_loaded:
            return
        path = _index_path(self.session_id, "semantic")
        if os.path.exists(path):
            try:
                self._semantic = NNIndex.load(path)
            except Exception:
                self._semantic = self._rebuild_semantic()
        else:
            self._semantic = self._rebuild_semantic()
        self._semantic_loaded = True

    def _ensure_episodic(self):
        if self._episodic_loaded:
            return
        path = _index_path(self.session_id, "episodic")
        if os.path.exists(path):
            try:
                self._episodic = NNIndex.load(path)
            except Exception:
                self._episodic = self._rebuild_episodic()
        else:
            self._episodic = self._rebuild_episodic()
        self._episodic_loaded = True

    def _ensure_segments(self):
        if self._segments_loaded:
            return
        path = _index_path(self.session_id, "segments")
        if os.path.exists(path):
            try:
                self._segments = NNIndex.load(path)
            except Exception:
                self._segments = self._rebuild_segments()
        else:
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
        ids = [r.id for r in rows]
        vecs = np.array([blob_to_vec(r.embedding_vector) for r in rows], dtype=np.float32)
        idx = NNIndex.build(ids, vecs)
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
        ids = [r.id for r in rows]
        vecs = np.array([blob_to_vec(r.embedding) for r in rows], dtype=np.float32)
        idx = NNIndex.build(ids, vecs)
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
        ids = [r.id for r in rows]
        vecs = np.array([blob_to_vec(r.embedding) for r in rows], dtype=np.float32)
        idx = NNIndex.build(ids, vecs)
        idx.save(_index_path(self.session_id, "segments"))
        return idx

    # ── Public search API ─────────────────────────────────────────────────────

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

    # ── Rebuild ───────────────────────────────────────────────────────────────

    def rebuild(self):
        self._semantic = self._rebuild_semantic()
        self._episodic = self._rebuild_episodic()
        self._segments = self._rebuild_segments()
        self._semantic_loaded = True
        self._episodic_loaded = True
        self._segments_loaded = True

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
