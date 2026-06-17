# FILE: app/api/utils.py
# DESCRIPTION: Shared utilities for API endpoints

from __future__ import annotations

from fastapi import Request
from app.db import ALL_TOOL_ROLES


def get_client_id(request: Request) -> str:
    """Generate a client identifier from request metadata.

    Used for web client session tracking to prevent duplicate connection messages.
    """
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    return f"{client_host}_{hash(user_agent) % 10000}"

def stitch_chat_history(messages: list[dict]) -> list[dict]:
    """
    Stitch tool execution results into the preceding assistant message.
    This mirrors the cohesive streaming behavior for the frontend UI.
    """
    stitched = []
    for msg in messages:
        role = msg.get("role")
        if (role in ALL_TOOL_ROLES or role == "tool" or role == "system_observation") and stitched and stitched[-1].get("role") == "assistant":
            if msg.get("content"):
                stitched[-1]["content"] = f"{stitched[-1].get('content', '')}\n\n{msg['content']}".strip()
        else:
            stitched.append(msg)
    return stitched
