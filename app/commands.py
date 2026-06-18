# FILE: app/commands.py
# DESCRIPTION: Image-path helpers + tool alias map for Yuzu Companion.
#              The legacy <command>...</command> text parser has been removed.
#              All tool invocation now uses native OpenAI tool_calls API.

from __future__ import annotations

import re

# Maximum chars for regex input to prevent ReDoS
_REGEX_INPUT_LIMIT = 100000

# Aliases the model uses for tool routing.
# Maps tool names from LLM output to registry tool names.
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

# Image shortcut warning
IMAGE_SHORTCUT_WARNING = (
    "\n\nImage output detected via incorrect method. "
    "Please use the image_generate tool for image generation."
)


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
    """True when the model emitted a raw ![](static/...) instead of using tool_calls."""
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
