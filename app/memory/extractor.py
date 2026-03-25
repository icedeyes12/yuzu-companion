# [FILE: memory/extractor.py]
# [DESCRIPTION: Memory extraction layer - semantic + episodic writers with embeddings]

import re
import math
import hashlib
from datetime import datetime

import numpy as np

from app.database import (
    get_db_session, SemanticMemory, EpisodicMemory
)
from app.memory.embedder import embed_text, vec_to_blob, blob_to_vec


def _get_ai_manager():
    """Lazy-import ai_manager to avoid circular imports."""
    from app import get_ai_manager
    return get_ai_manager()


# Keywords that indicate semantic facts — maps to memory_store taxonomy:
# Preference | Identity | Interest | Guideline | Goal | Relationship | Experience | Personality
_SEMANTIC_PATTERNS = [
    # Preference — positive
    (r'\b(?:i prefer|i like|i love|i enjoy|i want|i need|i usually go for)\b(.+)', 'Preference'),
    # Preference — negative (Dislikes stored as same category, confidence handles sign)
    (r'\b(?:i hate|i dislike|i don\'t like|i can\'t stand|i avoid|i never want)\b(.+)', 'Preference'),
    # Identity — who the user is
    (r'\b(?:i am|i\'m|my name is|i live in|i work at|i work as|i\'m a|i\'m an)\b(.+)', 'Identity'),
    # Experience — skills, tools, past work
    (r'\b(?:i use|i work with|i code in|i develop in|i\'ve built|i\'ve made|i built|i made)\b(.+)', 'Experience'),
    # Personality — behavioral patterns
    (r'\b(?:i always|i usually|i often|i tend to|i sometimes|i rarely|i never)\b(.+)', 'Personality'),
    # Interest — topics the user cares about learning/pursuing
    (r'\b(?:i\'m interested in|i want to learn|i\'m learning|i\'ve been studying|i\'m into)\b(.+)', 'Interest'),
    # Goal — aspirations and plans
    (r'\b(?:i want to|i\'m trying to|i\'m planning to|i\'m working on|i\'ll|i\'m going to)\b(.+)', 'Goal'),
    # Guideline — how the user wants to be treated/addressed
    (r'\b(?:call me|don\'t call me|don\'t|never|always|please|i prefer you)\b(.+)', 'Guideline'),
    # Relationship — people in user's life
    (r'\b(?:my girlfriend|my boyfriend|my partner|my wife|my husband|my friend|my mom|my dad|my sister|my brother)\b(.+)', 'Relationship'),
    # Indonesian patterns
    (r'\b(?:aku suka|aku lebih suka|gue suka|gua suka)\b(.+)', 'Preference'),
    (r'\b(?:aku benci|aku nggak suka|gue nggak suka|gua nggak suka|aku ogah)\b(.+)', 'Preference'),
    (r'\b(?:aku ini|gue ini|gua ini|aku namanya|gue namanya)\b(.+)', 'Identity'),
    (r'\b(?:aku pake|aku pakai|gue pake|gue pakai)\b(.+)', 'Experience'),
    (r'\b(?:aku selalu|gue selalu|aku biasanya|gue biasanya)\b(.+)', 'Personality'),
    (r'\b(?:aku mau|gue mau|aku pengen|gue pengen|aku lagi belajar)\b(.+)', 'Goal'),
]

_EMOTIONAL_KEYWORDS = [
    'angry', 'frustrated', 'sad', 'happy', 'excited', 'love',
    'hate', 'cry', 'laugh', 'upset', 'worried', 'scared',
    'marah', 'kesal', 'sedih', 'senang', 'sayang', 'benci',
    'takut', 'khawatir', 'kecewa',
]


def _compute_message_hash(messages: list) -> str:
    """Stable hash of message IDs (or content if no IDs) for dedupe."""
    try:
        ids = [str(m.get('id', m.get('content', ''))[:50]) for m in messages]
        return hashlib.sha256('|'.join(sorted(ids)).encode()).hexdigest()[:16]
    except Exception:
        return ''


def _llm_extract_facts(messages) -> list[dict]:
    """Use the LLM to extract semantic facts from user messages.

    Called as fallback when regex finds nothing.
    Returns a list of dicts: {entity, relation, target}
    """
    try:
        ai_manager = _get_ai_manager()
        conversation = '\n'.join(
            f"{'User' if m.get('role') == 'user' else 'AI'}: {m.get('content', '')}"
            for m in messages if m.get('role') in ('user', 'assistant')
        )
        prompt = (
            "Extract factual knowledge about the user from their messages above. "
            "Classify each fact using exactly one of these relation types:\n"
            "  - Preference: likes, dislikes, habits (e.g. 'Prefers dark mode')\n"
            "  - Identity: name, location, job, demographics (e.g. 'Is a developer')\n"
            "  - Interest: topics they want to learn or explore (e.g. 'Interested in AI')\n"
            "  - Guideline: how they want to be treated or addressed (e.g. 'Guideline: call me Bani')\n"
            "  - Goal: things they want to achieve or do (e.g. 'Goal: build an app')\n"
            "  - Relationship: people in their life (e.g. 'Relationship: girlfriend named Sari')\n"
            "  - Experience: skills, tools, past projects (e.g. 'Experience: uses Python')\n"
            "  - Personality: behavioral patterns and tendencies (e.g. 'Personality: works late nights')\n\n"
            "Return a JSON list of facts with entity (always 'User'), relation, and target (max 200 chars). "
            "Return an empty list if nothing meaningful can be extracted. "
            "Example: [{\"entity\": \"User\", \"relation\": \"Preference\", \"target\": \"Prefers dark mode\"}]"
        )
        response = ai_manager.send_message(
            provider=None,
            model=None,
            messages=[
                {"role": "system", "content": "You extract structured user facts from conversation using the taxonomy: Preference, Identity, Interest, Guideline, Goal, Relationship, Experience, Personality."},
                {"role": "user", "content": conversation + "\n\n" + prompt},
            ],
            timeout=30,
            max_tokens=300,
        )
        if not response:
            return []
        import json as _json
        facts = _json.loads(response)
        if isinstance(facts, list):
            return [f for f in facts if f.get('entity') and f.get('relation') and f.get('target')]
    except Exception as e:
        print(f"[WARNING] LLM fact extraction failed: {e}")
    return []


def extract_semantic_facts(messages):
    """Extract semantic triples from a list of messages.

    Tries regex first, then falls back to LLM extraction if no facts found.
    """
    facts = []
    for msg in messages:
        if msg.get('role') != 'user':
            continue
        content = msg.get('content', '')
        for pattern, relation in _SEMANTIC_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                target = match.group(1).strip()
                target = re.sub(r'[.,!?;:]+$', '', target).strip()
                if target and len(target) < 200:
                    facts.append({
                        'entity': 'User',
                        'relation': relation,
                        'target': target,
                    })

    # LLM fallback: if regex found nothing, try LLM extraction
    if not facts:
        llm_facts = _llm_extract_facts(messages)
        if llm_facts:
            facts.extend(llm_facts)

    return facts


def calculate_emotional_weight(messages):
    """Calculate emotional intensity from a list of messages. Returns 0.0–1.0."""
    if not messages:
        return 0.0
    total_hits = 0
    for msg in messages:
        content = msg.get('content', '').lower()
        for keyword in _EMOTIONAL_KEYWORDS:
            if keyword in content:
                total_hits += 1
    return min(total_hits / max(len(messages), 1) * 0.3, 1.0)


def should_create_episodic(messages, affection_delta=0):
    """Determine if an episodic memory should be created."""
    if not messages:
        return False
    emotional_weight = calculate_emotional_weight(messages)
    if emotional_weight >= 0.3:
        return True
    if len(messages) >= 10:
        return True
    if abs(affection_delta) >= 20:
        return True
    return False


def generate_episodic_summary(messages):
    """Generate a concise summary from a list of messages using LLM.

    Tries LLM summarization first; falls back to naive truncation on failure.
    """
    if not messages:
        return ""
    summary = _llm_summarize(messages)
    if summary:
        return summary
    return _truncate_summary(messages)


def _llm_summarize(messages) -> str | None:
    """Use the LLM to generate a concise summary of a message list.

    Sends the conversation to the AI and asks for a 1-3 sentence summary.
    Returns None on failure (falls back to truncation).
    """
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
        print(f"[WARNING] LLM summarization failed: {e}")
    return None


def _truncate_summary(messages):
    """Fallback: produce a naive text truncation when LLM is unavailable."""
    parts = []
    for msg in messages:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        if len(content) > 150:
            content = content[:150] + '...'
        if role in ('user', 'assistant'):
            label = 'User' if role == 'user' else 'AI'
            parts.append(f"{label}: {content}")
    if len(parts) > 6:
        return '\n'.join(parts[:3] + ['...'] + parts[-3:])
    return '\n'.join(parts)


def _build_semantic_text(entity, relation, target):
    """Build a searchable text from a semantic triple."""
    return f"{entity} {relation} {target}"


def _find_similar_semantic(session_id, entity, relation, target, vector, threshold=0.95) -> int | None:
    """
    Check if a semantically similar fact already exists for (entity, relation).
    Uses dot product on stored embedding vectors.
    Returns existing db id if similarity > threshold, else None.
    """
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


def upsert_semantic_memory(session_id, entity, relation, target):
    """Insert or update a semantic memory triple with embedding.

    Returns:
        tuple (db_id, embedding) — the memory id and its embedding vector,
        or (None, None) on failure. Callers use this to incrementally update
        the ANN index via IndexStore.add_semantic().
    """
    text = _build_semantic_text(entity, relation, target)
    vector = embed_text(text)  # Returns None gracefully if embedding fails

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
        else:
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
                importance=0.5,
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
    """Create a new episodic memory record with embedding.

    Returns:
        tuple (db_id, embedding) — the memory id and its embedding vector,
        or (None, None) on failure. Callers use this to incrementally update
        the ANN index via IndexStore.add_episodic().
    """
    vector = embed_text(summary)  # Returns None gracefully if embedding fails

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
                return  # already processed this exact batch
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
            )
            if mem_id is not None and vector is not None:
                try:
                    index_store.add_semantic(mem_id, np.array(vector, dtype=np.float32))
                except Exception as idx_err:
                    print(f"[WARNING] ANN index update failed (semantic): {idx_err}")
        except Exception as e:
            print(f"[WARNING] Semantic memory extraction failed: {e}")

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
                        print(f"[WARNING] ANN index update failed (episodic): {idx_err}")
            except Exception as e:
                print(f"[WARNING] Episodic memory creation failed: {e}")
