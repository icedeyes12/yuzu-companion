# FILE: app/skills/memory_pipeline.py
# DESCRIPTION: Skill helper for memory extraction, episodic sync, and decay.

from datetime import datetime

from app.database import Database


def run_memory_pipeline(
    session_id,
    state,
):
    """Run episodic + semantic memory extraction on recent messages."""
    from app.memory.extractor import should_create_episodic, calculate_emotional_weight
    from app.memory.extractor import generate_episodic_summary, create_episodic_memory
    from app.memory.extractor import extract_semantic_facts, upsert_semantic_memory
    from app.memory.review import run_decay

    recent = Database.get_chat_history(session_id=session_id, limit=20, recent=True)
    if not recent:
        return False

    recent_ids = [m["id"] for m in recent]

    if should_create_episodic(recent):
        emotional_weight = calculate_emotional_weight(recent)
        summary = generate_episodic_summary(recent)
        if summary:
            importance = 0.5 + emotional_weight * 0.3
            try:
                create_episodic_memory(
                    session_id,
                    summary,
                    emotional_weight,
                    importance,
                    source_message_ids=recent_ids,
                )
            except Exception as e:
                print(f"[WARNING] Episodic memory creation failed: {e}")

    semantic_last_run = state["semantic_last_run"]
    semantic_last_msg_count = state["semantic_last_msg_count"]
    last_decay_run = state["last_decay_run"]
    semantic_cooldown_msgs = state["semantic_cooldown_msgs"]
    decay_interval_hours = state["decay_interval_hours"]

    last_run = semantic_last_run.get(session_id)
    session_memory = Database.get_session_memory(session_id)
    msg_count = session_memory.get("message_count", 0) if session_memory else 0
    msg_delta = msg_count - semantic_last_msg_count.get(session_id, 0)
    time_ok = last_run is None or (datetime.now() - last_run).total_seconds() >= 300
    should_run_semantic = msg_delta >= semantic_cooldown_msgs and time_ok
    if should_run_semantic:
        try:
            facts = extract_semantic_facts(recent)
            for fact in facts:
                try:
                    upsert_semantic_memory(session_id, fact["entity"], fact["relation"], fact["target"])
                except (KeyError, ValueError) as e:
                    print(f"[WARNING] Semantic fact malformed: {e}")
                except Exception as e:
                    print(f"[WARNING] Semantic memory upsert failed: {e}")
            semantic_last_run[session_id] = datetime.now()
            semantic_last_msg_count[session_id] = msg_count
        except Exception as e:
            print(f"[WARNING] Per-message semantic extraction failed: {e}")

    try:
        last_decay = last_decay_run.get(session_id)
        now = datetime.now()
        if last_decay is None or (now - last_decay).total_seconds() >= decay_interval_hours * 3600:
            run_decay(session_id)
            last_decay_run[session_id] = now
    except Exception as e:
        print(f"[WARNING] Memory decay failed: {e}")

    return True
