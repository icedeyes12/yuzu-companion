# FILE: app/tools/memory_store.py
# DESCRIPTION: Memory store tool for persisting and retrieving memories

from app.database import Database
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

    # Delegate to upsert_semantic_memory so both write paths share the same
    # embedding text format ("User {category} {fact}") and cross-deduplicate.
    # ANN staleness is handled by upsert_semantic_memory's _invalidate_semantic().
    try:
        from app.memory.extractor import upsert_semantic_memory
        mem_id, vector = upsert_semantic_memory(
            session_id,
            entity="User",
            relation=category,
            target=fact,
            importance=importance,
        )
        if mem_id is None:
            return build_markdown_contract(
                "memory_store_tools",
                full_command,
                ["Error: Failed to store memory"],
                partner_name,
            )
        was_deduped = vector is None  # upsert returns (id, None) when deduped
        if was_deduped:
            # Deduped — upsert updated the DB but invalidated the ANN.
            # add_semantic would be a no-op (ID already in _ids); skip it.
            return build_markdown_contract(
                "memory_store_tools",
                full_command,
                [f"Already remembered"],
                partner_name,
            )
        # New insert — add to ANN index.
        if mem_id is not None and vector is not None:
            try:
                import numpy as np
                index_store = get_index_store(session_id)
                index_store.add_semantic(mem_id, np.array(vector, dtype=np.float32))
            except Exception as idx_err:
                print(f"[memory_store] ANN index update failed: {idx_err}")
        return build_markdown_contract(
            "memory_store_tools",
            full_command,
            [f"Stored: [{category}] {fact}"],
            partner_name,
        )
    except Exception as e:
        print(f"[memory_store] Store failed: {e}")
        return build_markdown_contract(
            "memory_store_tools",
            full_command,
            [f"Error: {e}"],
            partner_name,
        )
