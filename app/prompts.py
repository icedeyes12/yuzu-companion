# FILE: app/prompts.py
# DESCRIPTION: System-prompt assembly and message-context construction
#              for the chat LLM.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import os
from app.db import Database
from app.logging_config import get_logger

log = get_logger(__name__)

# ── Token Limits ══════════════════════════════
MAX_HISTORY_TOKENS = 15000


def _estimate_tokens(text: str) -> int:
    """Estimate token count for text.

    Uses 3 chars per token (conservative for mixed content).
    """
    if not text:
        return 0
    return len(text) // 3


def _trim_history_to_token_limit(
    messages: list[dict],
    max_tokens: int = MAX_HISTORY_TOKENS,
) -> list[dict]:
    """Trim message history to fit within token budget.

    Starts from recent messages and works backwards,
    keeping as many messages as fit within the limit.
    Preserves at least last 2 messages for context.

    Args:
        messages: List of message dicts with 'content' key
        max_tokens: Maximum tokens allowed for history

    Returns:
        Trimmed list of messages
    """
    if not messages:
        return messages

    # Calculate total tokens
    total_tokens = sum(_estimate_tokens(m.get("content", "")) for m in messages)

    if total_tokens <= max_tokens:
        return messages

    # Need to trim - keep most recent messages
    log.info(f"[Prompt] Trimming history: {total_tokens} > {max_tokens} tokens")

    trimmed = []
    token_count = 0

    # Work backwards from most recent
    for msg in reversed(messages):
        msg_tokens = _estimate_tokens(msg.get("content", ""))

        # Always keep at least last 2 messages
        if len(trimmed) < 2:
            trimmed.insert(0, msg)
            token_count += msg_tokens
        elif token_count + msg_tokens <= max_tokens:
            trimmed.insert(0, msg)
            token_count += msg_tokens
        else:
            break

    log.info(
        f"[Prompt] Trimmed: {len(messages)}->{len(trimmed)} msgs, "
        f"{total_tokens}->{token_count} tok"
    )
    return trimmed


def _format_relative_time(timestamp_str: str | None) -> str:
    """Convert ISO timestamp to human-readable relative time (timezone-aware).

    Uses pure Python datetime math. Treats naive timestamps as UTC.
    Example: "2 hours ago", "3 days ago", "Just now"
    """
    if not timestamp_str:
        return "Unknown"

    try:
        # Clean and parse timestamp
        ts_str = timestamp_str.strip()
        if not ts_str:
            return "Unknown"

        # Handle various ISO formats
        if "T" in ts_str:
            # ISO format: "2026-05-22T14:30:00"
            iso_str = ts_str.split("+")[0].split(".")[0]
            past = datetime.fromisoformat(iso_str)
        else:
            # Simple format: "2026-05-22 14:30:00"
            iso_str = ts_str.split("+")[0].split(".")[0]
            past = datetime.fromisoformat(iso_str)

        # If naive, assume UTC
        if past.tzinfo is None:
            past = past.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        seconds = int((now - past).total_seconds())

        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:
            weeks = seconds // 604800
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        else:
            months = seconds // 2592000
            return f"{months} month{'s' if months != 1 else ''} ago"
    except (ValueError, AttributeError):
        return "Unknown"


def _truncate(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


def _read_file_content(filepath: str, max_size: int = 50000) -> str:
    """Read file content with size limit. Returns empty string if file not found."""

    try:
        if not os.path.exists(filepath):
            return ""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(max_size)
            return content
    except Exception:  # noqa: BLE001
        return ""


async def _retrieve_memories_async(
    session_id: int, user_message: str | None, static_limit: int, dynamic_limit: int
) -> tuple[list[int], str, str]:
    """Combined retrieval with single embedding call (async)."""
    try:
        from app.memory.retrieval import (
            retrieve_memories_combined_async,
            _format_static_context,
            _format_dynamic_context,
        )

        static, dynamic = await retrieve_memories_combined_async(
            session_id,
            query=user_message,
            static_limit=static_limit,
            dynamic_limit=dynamic_limit,
        )

        ids = [m["id"] for m in static]
        static_text = _format_static_context(static)
        dynamic_text = _format_dynamic_context(dynamic)

        return ids, static_text, dynamic_text
    except Exception as e:  # noqa: BLE001
        log.warning("combined memory retrieval async failed: %s", e)
        return [], "", ""


async def _mark_facts_pending_async(static_ids: list[int], session_id: int) -> None:
    if not static_ids:
        return
    try:
        from app.memory.memory_review import mark_retrieved_as_pending_review_async

        await mark_retrieved_as_pending_review_async(static_ids, session_id)
    except Exception as e:  # noqa: BLE001
        log.warning("pending-review marking failed: %s", e)


async def _legacy_memory_block_async(profile: dict[str, Any], session_id: int) -> str:
    block = ""
    session_memory = await Database.get_session_memory_async(session_id)
    if session_memory and session_memory.get("session_context"):
        block += (
            f"\n\nBACKGROUND (recent context):\n{session_memory['session_context']}"
        )

    profile_memory = profile.get("memory") or {}
    summary = profile_memory.get("player_summary")
    if summary:
        block += f"\n\nABOUT {profile.get('display_name', 'the user')}:\n{summary}"

    facts = profile_memory.get("key_facts") or {}
    fact_lines: list[str] = []
    for label, key in (
        ("Likes", "likes"),
        ("Tends to be", "personality_traits"),
        ("Important memories", "important_memories"),
        ("Dislikes", "dislikes"),
    ):
        values = facts.get(key) or []
        if values:
            fact_lines.append(f"{label}: {', '.join(values)}")
    if fact_lines:
        block += "\n" + "\n".join(fact_lines)
    return block


async def _location_block_async() -> str:
    try:
        ctx = await Database.get_context_async()
        loc = (ctx or {}).get("location") or {}
    except Exception:  # noqa: BLE001
        return "Unknown"

    if loc.get("lat") and loc.get("lon"):
        return f"{loc['lat']}, {loc['lon']}"

    return "Unknown"


def _interface_block(interface: str) -> str:
    """Return operational interface constraints without emotional directives."""
    if interface.lower() == "terminal":
        return "TERMINAL (Raw CLI, text-only, fast execution)"
    elif interface.lower() == "web":
        return "WEB UI (Supports Markdown, Mermaid diagrams, images)"
    return interface.upper()


def _global_knowledge_block(profile: dict[str, Any]) -> str:
    """Persistent cross-session knowledge about the user.

    Uses `global_knowledge` JSONB column from profiles table.
    Contains identity, preferences, and facts that persist across all sessions.
    Independent from per-session memory (semantic_facts, episodes).
    """
    global_knowledge = profile.get("global_knowledge") or {}
    if isinstance(global_knowledge, str):
        import json

        try:
            global_knowledge = json.loads(global_knowledge)
        except Exception:
            return ""

    facts = global_knowledge.get("facts") or []
    if not facts:
        return ""

    lines = []
    for fact in facts:
        if isinstance(fact, dict):
            # Structured format: {"category": "...", "content": "..."}
            category = fact.get("category", "")
            content = fact.get("content", "")
            if content:
                lines.append(
                    f"- [{category}] {content}" if category else f"- {content}"
                )
        elif isinstance(fact, str):
            # Simple string format
            lines.append(f"- {fact}")

    if not lines:
        return ""

    return "\n\n **WHAT YOU SHOULD KNOW ABOUT YOUR HUMAN**\n" + "\n".join(lines)


async def _session_events_block_async(session_id: int) -> str:
    """Build meta-awareness block with recent session context.
    Strictly returns state data. Behavioral rules are handled in the main prompt.
    """
    sessions = await Database.get_recent_active_sessions_async(
        current_session_id=session_id, limit=5
    )

    lines = ["\n[SESSION TOPOLOGY]"]

    if not sessions:
        lines.append("  - No other active sessions in memory.")
        return "\n".join(lines)

    for s in sessions:
        s_id = s.get("id", "?")
        name = s.get("name", "Unnamed Session")
        rel_time = _format_relative_time(s.get("updated_at"))
        lines.append(f"  - Session [{s_id}] '{name}' (Last active: {rel_time})")

    return "\n".join(lines)


async def build_system_message_async(
    profile: dict[str, Any],
    session_id: int,
    interface: str,
    user_message: str | None,
    native_tools: bool = False,
) -> str:
    """Render the full system prompt for a chat turn (async).

    OPTIMIZED: Only includes tools that are relevant to the current context.
    This reduces token wastage by ~40% on average.
    """
    current_time = datetime.now().strftime("%A, %Y-%m-%d %H:%M:%S")

    # Combined retrieval - single embedding call for both static and dynamic
    # OPTIMIZATION: Reduced limits to prevent token bloat
    static_ids, static_context, dynamic_context = await _retrieve_memories_async(
        session_id,
        user_message,
        static_limit=7,
        dynamic_limit=5,
    )
    await _mark_facts_pending_async(static_ids, session_id)
    memory_block = (f"\n\n{static_context}" if static_context else "") + dynamic_context
    memory_block += await _legacy_memory_block_async(profile, session_id)

    from pathlib import Path

    prompt_path = Path(__file__).parent / "prompt.md"
    template = prompt_path.read_text(encoding="utf-8")

    return template.format(
        partner_name=profile["partner_name"],
        display_name=profile["display_name"],
        global_context=_global_knowledge_block(profile),
        memory_block=memory_block,
        current_time=current_time,
        location_block=await _location_block_async(),
        interface_block=_interface_block(interface),
        session_metadata=await _session_events_block_async(session_id),
    )


async def build_messages(
    profile: dict[str, Any],
    session_id: int,
    interface: str,
    user_message: str | None,
    include_image_paths: bool = False,
    native_tools: bool = False,
) -> list[dict[str, Any]]:
    """Build the full chat-completion messages list (async).

    OPTIMIZED: Reduced history limit to prevent context bloat.
    """
    system_message = await build_system_message_async(
        profile, session_id, interface, user_message, native_tools=native_tools
    )

    # HARD CAP: Limit history
    history = (
        await Database.get_chat_history_for_ai_async(
            session_id=session_id,
            limit=100,  # .Fetch more, then trim by tokens
            recent=True,
            include_image_paths=include_image_paths,
        )
    ) or []

    # Apply token-based trimming
    history = _trim_history_to_token_limit(history, MAX_HISTORY_TOKENS)

    messages = [{"role": "system", "content": system_message}]

    import re

    for m in history:
        content = m["content"]
        if native_tools and isinstance(content, str):
            # Strip hallucinated <tools>...</tools> and legacy <tool>...</tool> blocks from assistant history
            if m["role"] == "assistant":
                content = re.sub(r"<tools>.*?</tools>", "", content, flags=re.DOTALL)
                content = re.sub(
                    r"<tool>.*?</tool>", "", content, flags=re.DOTALL
                ).strip()

        role = m["role"]
        if native_tools and role.endswith("_tools"):
            role = "tool"

        entry = {"role": role, "content": content}
        if "image_paths" in m and m["image_paths"]:
            entry["image_paths"] = m["image_paths"]

        # Include native tool calling fields if present
        if "tool_calls" in m and m["tool_calls"]:
            entry["tool_calls"] = m["tool_calls"]
        if "tool_call_id" in m and m["tool_call_id"]:
            entry["tool_call_id"] = m["tool_call_id"]
        if "name" in m and m["name"]:
            entry["name"] = m["name"]

        messages.append(entry)

    return messages
