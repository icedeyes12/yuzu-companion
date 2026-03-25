# FILE: app/tools/memory_store.py
# DESCRIPTION: Memory store tool for persisting and retrieving memories

from datetime import datetime
from app.database import Database, get_db_session, SemanticMemory
from app.memory.embedder import embed_texts, cosine_similarity, blob_to_vec, vec_to_blob
from app.tools.registry import build_markdown_contract
from app.memory.index_store import get_index_store


def _get_ai_manager():
    """Lazy-import ai_manager to avoid circular imports."""
    from app import get_ai_manager
    return get_ai_manager()


def _classify_fact(fact: str) -> tuple[str, float]:
    """Classify a fact category and rate its importance (0.0–1.0) using LLM.

    Returns (category, importance).
    """
    try:
        ai_manager = _get_ai_manager()
        prompt = (
            f"Classify this fact and rate its importance to the user on a scale of 0.0 to 1.0.\n\n"
            f"Fact: \"{fact}\"\n\n"
            "Category must be exactly one of:\n"
            "  - Preference: likes, dislikes, habits\n"
            "  - Identity: name, location, job, demographics\n"
            "  - Interest: topics they want to learn or explore\n"
            "  - Guideline: how they want to be treated or addressed\n"
            "  - Goal: things they want to achieve or do\n"
            "  - Relationship: people in their life\n"
            "  - Experience: skills, tools, past projects\n"
            "  - Personality: behavioral patterns and tendencies\n\n"
            "Importance scale:\n"
            "  - 0.0–0.3: minor preference or casual mention\n"
            "  - 0.4–0.6: regular knowledge about the user\n"
            "  - 0.7–1.0: core identity, goals, or emotionally significant\n\n"
            "Return ONLY a JSON object with keys 'category' and 'importance'. No other text.\n"
            'Example: {"category": "Preference", "importance": 0.7}'
        )
        response = ai_manager.send_message(
            provider=None,
            model=None,
            messages=[
                {"role": "system", "content": "You classify user facts and rate their importance. Output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            timeout=15,
            max_tokens=100,
        )
        if response:
            import json as _json
            result = _json.loads(response.strip())
            cat = result.get('category', 'Identity')
            imp = float(result.get('importance', 0.5))
            imp = max(0.0, min(1.0, imp))
            return cat, imp
    except Exception as e:
        print(f"[WARNING] LLM classification failed: {e}")
    return 'Identity', 0.5


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

    # Use LLM for category + importance unless user explicitly provided category
    if arguments.get("category"):
        category = arguments["category"]
        importance = 0.5
    else:
        category, importance = _classify_fact(fact)

    full_command = f'/memory_store fact="{fact[:60]}" category={category}'

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
                    import numpy as np
                    index_store.add_semantic(duplicate_id, np.array(vec, dtype=np.float32))
                except Exception:
                    pass
            return build_markdown_contract(
                "memory_store_tools",
                full_command,
                [f"Already remembered (confidence {rec.confidence:.2f})"],
                partner_name,
            )

        # Insert new fact — importance set by LLM
        new_mem = SemanticMemory(
            session_id=session_id,
            entity="User",
            relation=category,
            target=fact,
            confidence=0.7,
            importance=importance,
            embedding_vector=vector_blob,
            last_accessed=datetime.now(),
            access_count=1,
        )
        session.add(new_mem)
        session.commit()
        try:
            import numpy as np
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
