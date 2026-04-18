# FILE: app/commands.py
# DESCRIPTION: /command detection, dispatch, and markdown-image guards.
#              All pure helpers - no side effects beyond logging and tool dispatch.

from __future__ import annotations

import json
import re
from typing import Any

from app.logging_config import get_logger
from app.tools.registry import execute_tool

log = get_logger(__name__)

# Tools whose argument is a free-form string keyed by a specific field.
_STRING_ARG_TOOLS: dict[str, str] = {
    "imagine": "prompt",
    "request": "url",
    "memory_store": "fact",
}

# Aliases the model uses for tool routing.
_TOOL_ALIASES: dict[str, str] = {
    "imagine": "image_generate",
}

_MARKDOWN_IMAGE_PATH = re.compile(
    r'!\[[^\]]*\]\((static/|uploads/|generated_images/)[^)]+\)'
)
_MARKDOWN_IMAGE_ANY = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')
_GENERATED_IMAGE_SRC = re.compile(r'src="(static/generated_images/[^"]+)"')


def detect_command(response_text: str | None) -> dict[str, str] | None:
    """Return command info if response begins with a /command line, else None.

    Returned dict shape: {"command": str, "args": str, "full_command": str}.
    """
    if not response_text or not response_text.strip():
        return None
    first_line = response_text.split("\n", 1)[0].strip()
    if not first_line.startswith("/"):
        return None
    parts = first_line.split(None, 1)
    return {
        "command": parts[0][1:],
        "args": parts[1] if len(parts) > 1 else "",
        "full_command": first_line,
    }


def _parse_args(tool_name: str, args_str: str) -> dict[str, Any]:
    """Parse a /command argument string into a kwargs dict for the tool."""
    if not args_str:
        return {}
    if tool_name in _STRING_ARG_TOOLS:
        return {_STRING_ARG_TOOLS[tool_name]: args_str}
    try:
        parsed = json.loads(args_str)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {"query": args_str}


def execute_command(
    command_info: dict[str, str],
    session_id: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Resolve and execute a detected command.

    Returns (executed_tool_name, raw_tool_result_dict).
    """
    raw_name = command_info["command"]
    tool_name = _TOOL_ALIASES.get(raw_name, raw_name)
    args = _parse_args(raw_name, command_info["args"])
    log.info("command: /%s %s", raw_name, command_info["args"])
    result = execute_tool(tool_name, args, session_id=session_id)
    return tool_name, result


def parse_image_path(formatted_result: str) -> str | None:
    """Extract a generated-image path from a tool-contract markdown blob."""
    if not formatted_result:
        return None
    match = _GENERATED_IMAGE_SRC.search(formatted_result)
    return match.group(1) if match else None


def is_markdown_image_shortcut(response_text: str | None) -> bool:
    """True when the model emitted a raw ![](static/...) instead of /imagine."""
    if not response_text:
        return False
    return bool(_MARKDOWN_IMAGE_PATH.search(response_text))


def extract_markdown_image_path(response_text: str) -> str | None:
    """Return the first markdown image path/URL in *response_text*, if any."""
    match = _MARKDOWN_IMAGE_ANY.search(response_text)
    return match.group(1) if match else None


IMAGE_SHORTCUT_WARNING = (
    "\n\nImage output detected via incorrect method. "
    "Please use /imagine to generate images."
)
