# FILE: app/skills/memory_curation.py
# DESCRIPTION: Skill helper for profile-memory cleanup, normalization, and parsing.

from __future__ import annotations

from datetime import datetime
from typing import Dict, List


def normalize_memory_item(text: str) -> str:
    """Normalize a memory item for deduplication comparison."""
    text = text.strip().lower()
    text = _collapse_spaces(text)
    text = text.rstrip('.,"\'')
    return text


def merge_and_clean_memory(existing_list: List[str], new_items: List[str], max_size: int) -> List[str]:
    """Merge new items into an existing list with normalization-based deduplication and size limits."""
    result: List[str] = []
    seen_normalized: set[str] = set()

    for item in existing_list:
        if not item or not item.strip():
            continue
        norm = normalize_memory_item(item)
        if norm and norm not in seen_normalized:
            seen_normalized.add(norm)
            result.append(item)

    for item in new_items:
        if not item or not item.strip():
            continue
        norm = normalize_memory_item(item)
        if norm and norm not in seen_normalized:
            seen_normalized.add(norm)
            result.append(item)

    return result[:max_size]


def merge_profile_data(existing_memory: Dict, new_data: Dict) -> Dict:
    """Smart merge of existing profile data with new analysis."""
    if not existing_memory:
        return new_data

    result = existing_memory.copy()

    if new_data.get("player_summary"):
        existing_summary = result.get("player_summary", "")
        new_summary = new_data["player_summary"]
        if len(new_summary) > len(existing_summary) * 1.5:
            result["player_summary"] = new_summary
            print(f"[INFO] Updated player summary (new: {len(new_summary)} chars, old: {len(existing_summary)} chars)")

    if new_data.get("relationship_dynamics"):
        result["relationship_dynamics"] = new_data["relationship_dynamics"]

    if "key_facts" in new_data:
        if "key_facts" not in result:
            result["key_facts"] = {
                "likes": [],
                "dislikes": [],
                "personality_traits": [],
                "important_memories": [],
            }

        limits = {
            "likes": 30,
            "dislikes": 30,
            "personality_traits": 15,
            "important_memories": 20,
        }

        for category in ["likes", "dislikes", "personality_traits", "important_memories"]:
            existing_items = result["key_facts"].get(category, [])
            new_items = new_data["key_facts"].get(category, [])
            merged = merge_and_clean_memory(existing_items, new_items, limits[category])
            result["key_facts"][category] = merged

    result["last_global_summary"] = new_data.get("last_global_summary", "")
    result["sessions_analyzed"] = new_data.get("sessions_analyzed", 0)
    return result


def parse_global_profile_summary(summary_text: str) -> Dict:
    """Parse the global profile summary text into structured data."""
    profile_data = {
        "player_summary": "",
        "key_facts": {
            "likes": [],
            "dislikes": [],
            "personality_traits": [],
            "important_memories": [],
        },
        "relationship_dynamics": "",
        "last_updated": datetime.now().isoformat(),
    }

    cleaned_text = summary_text.replace("\r\n", "\n").replace("\r", "\n")

    section_patterns = {
        "Player Summary:": "player_summary",
        "Player Summary": "player_summary",
        "Summary:": "player_summary",
        "Summary": "player_summary",
        "Likes:": "likes",
        "Likes": "likes",
        "Interests:": "likes",
        "Interests": "likes",
        "Dislikes:": "dislikes",
        "Dislikes": "dislikes",
        "Aversions:": "dislikes",
        "Personality Traits:": "personality_traits",
        "Personality Traits": "personality_traits",
        "Traits:": "personality_traits",
        "Personality:": "personality_traits",
        "Important Memories:": "important_memories",
        "Important Memories": "important_memories",
        "Memories:": "important_memories",
        "Key Memories:": "important_memories",
        "Relationship Dynamics:": "relationship_dynamics",
        "Relationship Dynamics": "relationship_dynamics",
        "Relationship:": "relationship_dynamics",
        "Dynamics:": "relationship_dynamics",
    }

    lines = cleaned_text.split("\n")
    current_section = None
    buffer: List[str] = []

    def save_current_section() -> None:
        if current_section and buffer:
            content = " ".join(buffer).strip()
            if current_section == "player_summary":
                profile_data["player_summary"] = content
            elif current_section == "relationship_dynamics":
                profile_data["relationship_dynamics"] = content
            elif current_section in ["likes", "dislikes", "personality_traits", "important_memories"]:
                items = [item.strip() for item in content.split(",") if item.strip()]
                profile_data["key_facts"][current_section] = items

    for line in lines:
        line = line.strip()
        if not line:
            continue

        section_found = False
        for pattern, section_key in section_patterns.items():
            if line.startswith(pattern):
                save_current_section()
                current_section = section_key
                buffer = []
                remaining = line[len(pattern):].strip()
                if remaining:
                    buffer.append(remaining)
                section_found = True
                break

        if not section_found and current_section:
            buffer.append(line)

    save_current_section()

    for section in ["player_summary", "relationship_dynamics"]:
        if profile_data[section]:
            profile_data[section] = profile_data[section].strip()
            if profile_data[section].endswith("."):
                profile_data[section] = profile_data[section][:-1]

    for key in ["likes", "dislikes", "personality_traits", "important_memories"]:
        if profile_data["key_facts"][key]:
            unique_items: List[str] = []
            seen = set()
            for item in profile_data["key_facts"][key]:
                if item and item not in seen:
                    seen.add(item)
                    unique_items.append(item)
            profile_data["key_facts"][key] = unique_items

    print(
        f"[DEBUG] Parsed profile: player_summary={len(profile_data['player_summary'])} chars, "
        f"likes={len(profile_data['key_facts']['likes'])}, "
        f"personality_traits={len(profile_data['key_facts']['personality_traits'])}"
    )

    return profile_data


def _collapse_spaces(text: str) -> str:
    return " ".join(text.split())
