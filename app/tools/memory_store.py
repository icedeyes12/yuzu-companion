from datetime import datetime
from app.database import Database, get_db_session, SemanticMemory
from app.memory.embedder import embed_texts, cosine_similarity, blob_to_vec, vec_to_blob
from app.tools.registry import build_markdown_contract
import numpy as np
from app.memory.index_store import get_index_store


def _infer_category(fact):
    s = fact.lower()
    if any(w in s for w in ["prefer", "like", "love", "hate", "dislike", "favorite", "enjoy"]):
        return "Preference"
    if any(w in s for w in ["name", "live", "work", "job", "career", "company", "city", "age", "born"]):
        return "Identity"
    if any(w in s for w in ["interest", "hobby", "learn", "study", "passion"]):
        return "Interest"
    if any(w in s for w in ["should", "avoid", "never", "always", "tone", "behave", "call me"]):
        return "Guideline"
    if any(w in s for w in ["goal", "plan", "want", "aspire", "dream"]):
        return "Goal"
    if any(w in s for w in ["family", "friend", "partner", "relationship", "girlfriend", "boyfriend"]):
        return "Relationship"
    if any(w in s for w in ["skill", "experience", "past project", "built", "made"]):
        return "Experience"
    if any(w in s for w in ["personality", "style", "tend", "usually", "often", "communicat"]):
        return "Personality"
    return "Identity"


def execute(arguments, **kwargs):
    session_id = kwargs.get("session_id")
    profile = Database.get_profile() or {}
    partner_name = profile.get("partner_name", "Yuzu")

    fact = arguments.get("fact", "").strip()
    if not fact:
        return build_markdown_contract(
            "memory_store_tools",
            "/memory_store",
            ["Error: 'fact' is required"],
            partner_name,
        )

    if len(fact) < 5:
        return build_markdown_contract(
            "memory_store_tools",
            "/memory_store",
            ["Error: Fact too short (min 5 chars)"],
            partner_name,
        )

    if len(fact) > 500:
        return build_markdown_contract(
            "memory_store_tools",
            "/memory_store",
            ["Error: Fact too long (max 500 chars)"],
            partner_name,
        )

    category = arguments.get("category", _infer_category(fact))
    full_command = f"/memory_store fact=\"{fact[:60]}\" category={category}"

    # Embed the fact text — store as BLOB for ANN index compatibility
    embed_label = f"[{category}] {fact}"
    try:
        vecs = embed_texts([embed_label])
        vec = vecs[0]
        vector_blob = vec_to_blob(vec)
    except Exception as e:
        print(f"[memory_store] Embed failed: {e}")
        return build_markdown_contract(
            "memory_store_tools",
            full_command,
            ["Error: Embedding service unavailable"],
            partner_name,
        )

    with get_db_session() as session:
        existing = session.query(SemanticMemory).filter(
            SemanticMemory.session_id == session_id,
        ).all()

        duplicate_id = None
        for rec in existing:
            if rec.embedding_vector:
                try:
                    rec_vec = blob_to_vec(rec.embedding_vector)
                    sim = cosine_similarity(vec, rec_vec)
                    if sim > 0.95:
                        duplicate_id = rec.id
                        break
                except Exception:
                    pass

        index_store = get_index_store(session_id)

        if duplicate_id:
            rec = session.query(SemanticMemory).filter_by(id=duplicate_id).first()
            if rec:
                rec.confidence = min((rec.confidence or 0.5) + 0.1, 1.0)
                rec.access_count = (rec.access_count or 0) + 1
                rec.last_accessed = datetime.now()
                rec.embedding_vector = vector_blob
                session.commit()
                try:
                    index_store.add_semantic(duplicate_id, np.array(vec, dtype=np.float32))
                except Exception:
                    pass
            return build_markdown_contract(
                "memory_store_tools",
                full_command,
                [f"Already remembered (confidence {rec.confidence:.2f})"],
                partner_name,
            )

        # Insert new fact
        new_mem = SemanticMemory(
            session_id=session_id,
            entity="User",
            relation=category,
            target=fact,
            confidence=0.7,
            importance=0.6,
            embedding_vector=vector_blob,
            last_accessed=datetime.now(),
            access_count=1,
        )
        session.add(new_mem)
        session.commit()
        try:
            db_id = session.query(SemanticMemory.id).filter(
                SemanticMemory.session_id == session_id,
                SemanticMemory.entity == "User",
                SemanticMemory.relation == category,
                SemanticMemory.target == fact,
            ).scalar()
            if db_id:
                index_store.add_semantic(db_id, np.array(vec, dtype=np.float32))
        except Exception:
            pass

    return build_markdown_contract(
        "memory_store_tools",
        full_command,
        [f"Stored: [{category}] {fact}"],
        partner_name,
    )
