# FILE: app/commands.py
# DESCRIPTION: Direct-user-input helpers for the orchestrator's fast-path.
#              As of Phase E (native tool calling), the LLM-side <command>...</command>
#              parser has been REMOVED. Tools are now invoked through the OpenAI
#              native tool_calls protocol surfaced by AsyncOpenAI.
#
# This module retains:
#   - The /imagine fast-path alias map (alias -> canonical tool name)
#   - Markdown image helpers for post-processing the assistant's text
#   - IMAGE_SHORTCUT_WARNING for the markdown-image-shortcut guard
#
# All other functions were removed because the SDK now handles argument parsing,
# dispatch, and tool_call_id stitching natively.

from __future__ import annotations

import re

from app.logging_config import get_logger

log = get_logger(__name__)

# --------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------

# Maximum chars for regex input to prevent ReDoS
_REGEX_INPUT_LIMIT = 100000

# Aliases the user (typed directly) uses for tool routing.
# Maps raw user input (e.g. "/imagine ...") to canonical registry tool names.
# This is for the direct user input fast-path ONLY — LLM output goes through
# the OpenAI native tool_calls protocol.
_TOOL_ALIASES: dict[str, str] = {
    "imagine": "image_generate",
    "image_generate": "image_generate",
    "http_request": "http_request",
    "request": "http_request",  # Alias for http_request
    "ask-rei": "ask_rei",
}

# Image path patterns for result parsing
_GENERATED_IMAGE_SRC = re.compile(r'src="(static/generated_images/[^"]+)"')
_MARKDOWN_IMAGE_PATH = re.compile(
    r"!\[[^\]]{0,200}\]\((static/|uploads/|generated_images/)[^)]{1,200}\)"
)
_MARKDOWN_IMAGE_ANY = re.compile(r"!\[[^\]]{0,200}\]\(([^)]{1,200})\)")

# Image shortcut warning — the model emitted a raw ![](static/...) instead of
# using the native tool_calls protocol. This is a model misbehaviour guard, not
# a parser input. (Kept from previous version for parity.)
IMAGE_SHORTCUT_WARNING = (
    "\n\nImage output detected via incorrect method. "
    "Please use the native image_generate tool for image generation."
)


# --------------------------------------------------------------------
# Safe regex helper
# --------------------------------------------------------------------


def _safe_regex_search(pattern: re.Pattern, text: str) -> re.Match | None:
    """Safely search with input length limit to prevent ReDoS."""
    if len(text) > _REGEX_INPUT_LIMIT:
        text = text[:_REGEX_INPUT_LIMIT]
    return pattern.search(text)


# --------------------------------------------------------------------
# Direct user input parsing (fast-path for typed /imagine shortcuts)
# --------------------------------------------------------------------


def _parse_user_fastpath_command(command_str: str) -> dict[str, str] | None:
    """Parse a DIRECTLY typed user command (e.g. '/imagine prompt here').

    This is the only remaining string-split parser, scoped narrowly to the
    /imagine fast-path in handle_user_message. The LLM does NOT go through
    this — the LLM uses the OpenAI native tool_calls protocol exclusively.

    Command format: /command_name args...
    or just: command_name args...

    Returns None if the command string is invalid.
    """
    stripped = command_str.strip()
    if not stripped:
        return None

    # Handle /command format (e.g. /imagine foo)
    if stripped.startswith("/"):
        stripped = stripped[1:]

    # Split into command name and args
    parts = stripped.split(None, 1)
    if not parts:
        return None

    command_name = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    return {
        "command": command_name,
        "args": args,
        "full_command": f"/{command_name} {args}".strip(),
    }


def _resolve_user_alias(raw_name: str) -> str:
    """Resolve a direct user-typed tool alias to its canonical name."""
    return _TOOL_ALIASES.get(raw_name, raw_name)


# --------------------------------------------------------------------
# Image Helpers
# --------------------------------------------------------------------


def parse_image_path(formatted_result: str) -> str | None:
    """Extract and validate a generated-image path from markdown blob."""
    if not formatted_result:
        return None

    match = _GENERATED_IMAGE_SRC.search(formatted_result)
    if not match:
        return None

    raw_path = match.group(1).strip()
    if not raw_path:
        return None

    # Normalize separators and reject absolute/escape paths
    candidate = raw_path.replace("\\", "/")
    if candidate.startswith("/") or candidate.startswith("../") or "/../" in candidate:
        return None
    if "/./" in candidate or candidate.endswith("/.") or candidate.endswith("/.."):
        return None

    # Allow only known local roots used by the app for generated/served images
    if not (candidate.startswith("static/") or candidate.startswith("uploads/")):
        return None

    # Restrict to common image file extensions
    lowered = candidate.lower()
    if not lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return None

    return candidate


def is_markdown_image_shortcut(response_text: str | None) -> bool:
    """True when the model emitted a raw ![](static/...) instead of native tool_calls."""
    if not response_text:
        return False
    if len(response_text) > _REGEX_INPUT_LIMIT:
        response_text = response_text[:_REGEX_INPUT_LIMIT]
    return bool(_MARKDOWN_IMAGE_PATH.search(response_text))


def extract_markdown_image_path(response_text: str) -> str | None:
    """Return the first markdown image path/URL in *response_text*, if any."""
    if len(response_text) > _REGEX_INPUT_LIMIT:
        response_text = response_text[:_REGEX_INPUT_LIMIT]
    match = _MARKDOWN_IMAGE_ANY.search(response_text)
    return match.group(1) if match else None


# --------------------------------------------------------------------
# LLM-side <command> parser: REMOVED in Phase E
# --------------------------------------------------------------------
# The following functions have been removed because Phase E migrates tool
# invocation to the OpenAI native tool_calls protocol (AsyncOpenAI):
#   - parse_tool_blocks(): the <command>...</command> line-start parser
#   - has_tool_blocks(): line-start detection helper
#   - _parse_command_string: command-name + args splitter (LLM-side)
#   - _parse_args: key=value/JSON arg splitter
#   - _parse_key_value_args: key="value with spaces" splitter
#   - execute_commands: sequential LLM-output tool dispatcher
#   - format_observation: <SYSTEM_OBSERVATION> markdown wrapper
#   - _TOOL_OPEN / _TOOL_CLOSE: <command>/</command> tag constants
#   - _STRING_ARG_TOOLS: per-tool free-form-arg key map
#
# The orchestrator now intercepts ChatCompletion.choices[0].message.tool_calls
# directly and stitches tool results into ephemeral_context as:
#   {"role": "tool", "tool_call_id": tc.id, "content": ...}
#
# Direct user-typed shortcuts (e.g. /imagine foo) still resolve via
# _parse_user_fastpath_command() + _resolve_user_alias() in the orchestrator's
# handle_user_message fast-path.
