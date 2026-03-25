# [FILE: memory/extractor.py]
# [DESCRIPTION: Memory extraction layer - semantic + episodic writers with embeddings]

import logging

import math
import hashlib
from datetime import datetime

import numpy as np

from app.database import (
    get_db_session, SemanticMemory, EpisodicMemory
)
from app.memory.embedder import embed_text, vec_to_blob, blob_to_vec

logger = logging.getLogger(__name__)

# Session-scoped extraction error counter — reset per process
_extraction_errors: int = 0


def get_extraction_error_count() -> int:
    """Return the number of extraction errors seen this process."""
    return _extraction_errors


def _get_ai_manager():
    """Lazy-import ai_manager to avoid circular imports."""
    from app import get_ai_manager
    return get_ai_manager()


def _compute_message_hash(messages: list) -> str:
    """Stable hash of message IDs (or content if no IDs) for dedupe."""
    try:
        ids = [str(m.get('id', m.get('content', ''))[:50]) for m in messages]
        return hashlib.sha256('|'.join(sorted(ids)).encode()).hexdigest()[:16]
    except Exception:
        return ''


def extract_semantic_facts(messages) -> list[dict]:
    """Extract semantic triples from user messages using LLM only.

    Returns a list of dicts: {entity, relation, target, importance}
    - importance: 0.0–1.0, how central/key the fact is to the user's identity
    Taxonomy: Preference | Identity | Interest | Guideline | Goal | Relationship | Experience | Personality
    """
    try:
        ai_manager = _get_ai_manager()
        conversation = '\n'.join(
            f"{'User' if m.get('role') == 'user' else 'AI'}: {m.get('content', '')}"
            for m in messages if m.get('role') in ('user', 'assistant')
        )
        prompt = (
            "You extract factual knowledge about the user from their messages above.\n"
            "For each fact, also rate its importance on a scale of 0.0 to 1.0:\n"
            "  - 0.0–0.3: minor preference or casual mention (e.g. 'likes tea')\n"
            "  - 0.4–0.6: regular knowledge about the user (e.g. 'lives in Jakarta', 'works as developer')\n"
            "  - 0.7–1.0: core identity, goals, or emotionally significant (e.g. 'Goal: build a startup', 'girlfriend named Sari')\n\n"
            "Classify each fact using exactly one of these relation types:\n"
            "  - Preference: likes, dislikes, habits (e.g. 'Prefers dark mode')\n"
            "  - Identity: name, location, job, demographics (e.g. 'Is a developer' or 'Lives in Jakarta')\n"
            "  - Interest: topics they want to learn or explore (e.g. 'Interested in AI' or 'Wants to learn Python')\n"
            "  - Guideline: how they want to be treated or addressed (e.g. 'Guideline: call me Bani')\n"
            "  - Goal: things they want to achieve or do (e.g. 'Goal: build an app' or 'Planning to start a business')\n"
            "  - Relationship: people in their life (e.g. 'Relationship: girlfriend named Sari')\n"
            "  - Experience: skills, tools, past projects (e.g. 'Experience: uses Python' or 'Built a React app')\n"
            "  - Personality: behavioral patterns and tendencies (e.g. 'Personality: works late nights')\n\n"
            "Return a JSON list of facts with entity (always 'User'), relation, target (max 200 chars), and importance (float 0.0–1.0).\n"
            "Return an empty list [] if nothing meaningful can be extracted.\n"
            "Only extract facts explicitly stated or strongly implied — do not guess or generalize.\n\n"
            "Example input: \"I love coding in Python late at night, I'm Bani from Jakarta, my goal is to ship yuzu-v2\"\n"
            "Example output: [\n"
            "  {\"entity\": \"User\", \"relation\": \"Preference\", \"target\": \"Loves coding in Python\", \"importance\": 0.6},\n"
            "  {\"entity\": \"User\", \"relation\": \"Identity\", \"target\": \"Name is Bani, from Jakarta\", \"importance\": 0.7},\n"
            "  {\"entity\": \"User\", \"relation\": \"Personality\", \"target\": \"Works late at night\", \"importance\": 0.5},\n"
            "  {\"entity\": \"User\", \"relation\": \"Goal\", \"target\": \"Ship yuzu-v2\", \"importance\": 0.9}\n"
            "]"
        )
        response = ai_manager.send_message(
            provider=None,
            model=None,
            messages=[
                {"role": "system", "content": "You extract structured user facts from conversation. Use the taxonomy: Preference, Identity, Interest, Guideline, Goal, Relationship, Experience, Personality. Also rate importance 0.0–1.0."},
                {"role": "user", "content": conversation + "\n\n" + prompt},
            ],
            timeout=30,
            max_tokens=600,
        )
        if not response:
            return []
        import json as _json
        facts = _json.loads(response)
        if isinstance(facts, list):
            return [
                f for f in facts
                if f.get('entity') and f.get('relation') and f.get('target')
            ]
    except Exception as e:
        logger.warning(f"LLM fact extraction failed: {e}")
        global _extraction_errors
        _extraction_errors += 1
    return []


def calculate_emotional_weight(messages) -> float:
    """Calculate emotional intensity using LLM. Returns 0.0–1.0."""
    if not messages:
        return 0.0
    try:
        ai_manager = _get_ai_manager()
        conversation = '\n'.join(
            f"{'User' if m.get('role') == 'user' else 'AI'}: {m.get('content', '')}"
            for m in messages if m.get('role') in ('user', 'assistant')
        )
        prompt = (
            "Rate the emotional intensity of this conversation on a scale of 0.0 to 1.0.\n"
            "0.0 = completely neutral, 1.0 = highly emotional (angry, upset, frustrated, excited, crying, etc.)\n"
            "Only return a single float number, nothing else. Example: 0.7"
        )
        response = ai_manager.send_message(
            provider=None,
            model=None,
            messages=[
                {"role": "system", "content": "You rate emotional intensity of conversations. Output only a single float 0.0–1.0."},
                {"role": "user", "content": conversation + "\n\n" + prompt},
            ],
            timeout=15,
            max_tokens=10,
        )
        if response:
            import re as _re
            match = _re.search(r'0?\.\d+', response.strip())
            if match:
                return float(match.group())
    except Exception as e:
        logger.warning(f"LLM emotional weight failed: {e}")
        _extraction_errors += 1
    return 0.0


def should_create_episodic(messages, affection_delta=0) -> bool:
    """Determine if an episodic memory should be created."""
    if not messages:
        return False
    emotional_weight = calculate_emotional_weight(messages)
    if emotional_weight >= 0.4:
        return True
    if len(messages) >= 10:
        return True
    if abs(affection_delta) >= 20:
        return True
    return False


def generate_episodic_summary(messages) -> str:
    """Generate a concise summary from a list of messages using LLM."""
    if not messages:
        return ""
    try:
        ai_manager = _get_ai_manager()
        prompt_messages = [
            {"role": "system", "content": (
                "You are a memory summarizer. Read the conversation below and produce "
                "a concise 1-3 sentence summary that captures the key topic, any "
                "decisions made, and the user's emotional state. Be specific and factual. "
                "Do not add information not present in the conversation."
            )},
        ]
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if isinstance(content, list):
                content = ' '.join(
                    c.get('text', '') for c in content if c.get('type') == 'text'
                )
            if role in ('user', 'assistant'):
                label = 'User' if role == 'user' else 'AI'
                prompt_messages.append({"role": "user", "content": f"{label}: {content}"})

        response = ai_manager.send_message(
            provider=None,
            model=None,
            messages=prompt_messages,
            timeout=30,
            max_tokens=200,
        )
        if response and isinstance(response, str) and response.strip():
            return response.strip()
    except Exception as e:
        logger.warning(f"LLM summarization failed: {e}")
        _extraction_errors += 1
    return ""


def _build_semantic_text(entity, relation, target):
    """Build a searchable text from a semantic triple."""
    return f"{entity} {relation} {target}"


def _find_similar_semantic(session_id, entity, relation, target, vector, threshold=0.95) -> int | None:
    """Check if a semantically similar fact already exists for (entity, relation)."""
    if vector is None:
        return None
    try:
        norm_target = math.sqrt(sum(x * x for x in vector))
        if norm_target == 0:
            return None
        with get_db_session() as session:
            existing = session.query(SemanticMemory).filter(
                SemanticMemory.session_id == session_id,
                SemanticMemory.entity == entity,
                SemanticMemory.relation == relation,
            ).all()
            for mem in existing:
                if mem.embedding_vector is None:
                    continue
                mem_vec = blob_to_vec(mem.embedding_vector)
                norm_mem = math.sqrt(sum(x * x for x in mem_vec))
                if norm_mem == 0:
                    continue
                dot = sum(a * b for a, b in zip(vector, mem_vec))
                sim = dot / (norm_target * norm_mem)
                if sim > threshold:
                    return mem.id
    except Exception:
        pass
    return None


def upsert_semantic_memory(session_id, entity, relation, target, importance=0.5):
    """Insert or update a semantic memory triple with embedding."""
    text = _build_semantic_text(entity, relation, target)
    vector = embed_text(text)

    with get_db_session() as session:
        existing = session.query(SemanticMemory).filter(
            SemanticMemory.session_id == session_id,
            SemanticMemory.entity == entity,
            SemanticMemory.relation == relation,
            SemanticMemory.target == target,
        ).first()

        if existing:
            existing.confidence = min(existing.confidence + 0.1, 1.0)
            existing.access_count += 1
            existing.last_accessed = datetime.now()
            if vector is not None:
                existing.embedding_vector = vec_to_blob(vector)
            session.commit()
            session.expunge(existing)
            return existing.id, vector

        dup_id = _find_similar_semantic(session_id, entity, relation, target, vector)
        if dup_id is not None:
            existing_dup = session.query(SemanticMemory).filter(
                SemanticMemory.id == dup_id
            ).first()
            if existing_dup:
                existing_dup.confidence = min(existing_dup.confidence + 0.15, 1.0)
                existing_dup.access_count += 1
                existing_dup.last_accessed = datetime.now()
                session.commit()
                session.expunge(existing_dup)
                print(f"[MEMORY] Dedup: boosted similar fact id={dup_id} "
                      f"({entity} {relation} {target[:40]})")
                return dup_id, None

        new_mem = SemanticMemory(
            session_id=session_id,
            entity=entity,
            relation=relation,
            target=target,
            confidence=0.5,
            importance=importance,
            embedding_vector=vec_to_blob(vector) if vector is not None else None,
            last_accessed=datetime.now(),
            access_count=1,
        )
        session.add(new_mem)
        session.commit()
        db_id = new_mem.id
        session.expunge(new_mem)
        return db_id, vector


def create_episodic_memory(session_id, summary, emotional_weight=0.0, importance=0.5):
    """Create a new episodic memory record with embedding."""
    vector = embed_text(summary)

    with get_db_session() as session:
        mem = EpisodicMemory(
            session_id=session_id,
            summary=summary,
            embedding=vec_to_blob(vector) if vector is not None else None,
            importance=importance,
            emotional_weight=emotional_weight,
            last_accessed=datetime.now(),
            access_count=0,
        )
        session.add(mem)
        session.commit()
        db_id = mem.id
        session.expunge(mem)
        return db_id, vector


def process_messages_for_memory(session_id, messages, affection_delta=0):
    """Main entry point: analyze messages and extract memories."""
    if not messages:
        return

    msg_hash = _compute_message_hash(messages)
    if msg_hash:
        try:
            from app.database import Database
            session_mem = Database.get_session_memory(session_id)
            if session_mem.get('_last_extractor_hash') == msg_hash:
                return
            update_payload = dict(session_mem)
            update_payload['_last_extractor_hash'] = msg_hash
            Database.update_session_memory(session_id, update_payload)
        except Exception:
            pass

    from app.memory.index_store import get_index_store
    index_store = get_index_store(session_id)

    facts = extract_semantic_facts(messages)
    for fact in facts:
        try:
            mem_id, vector = upsert_semantic_memory(
                session_id,
                fact['entity'],
                fact['relation'],
                fact['target'],
                fact.get('importance', 0.5),
            )
            if mem_id is not None and vector is not None:
                try:
                    index_store.add_semantic(mem_id, np.array(vector, dtype=np.float32))
                except Exception as idx_err:
                    logger.warning(f"ANN index update failed (semantic): {idx_err}")
                    _extraction_errors += 1
        except Exception as e:
            logger.warning(f"Semantic memory extraction failed: {e}")
            _extraction_errors += 1

    if should_create_episodic(messages, affection_delta):
        emotional_weight = calculate_emotional_weight(messages)
        summary = generate_episodic_summary(messages)
        if summary:
            try:
                importance = 0.5 + emotional_weight * 0.3
                mem_id, vector = create_episodic_memory(
                    session_id, summary, emotional_weight, importance
                )
                if mem_id is not None and vector is not None:
                    try:
                        index_store.add_episodic(mem_id, np.array(vector, dtype=np.float32))
                    except Exception as idx_err:
                        logger.warning(f"ANN index update failed (episodic): {idx_err}")
                        _extraction_errors += 1
            except Exception as e:
                logger.warning(f"Episodic memory creation failed: {e}")
                _extraction_errors += 1
