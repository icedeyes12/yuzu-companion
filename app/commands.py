# FILE: app/commands.py
# DESCRIPTION: /command detection, dispatch, and markdown-image guards.
#              All pure helpers - no side effects beyond log

from __future__ import annotations

import json
import re
from enum import Enum, auto
from typing import Any, Iterator

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
# These map /command names to registry tool names.
_TOOL_ALIASES: dict[str, str] = {
    "imagine": "image_generate",
    "image_generate": "image_generate",
}

_MARKDOWN_IMAGE_PATH = re.compile(
    r'!\[[^\]]{0,200}\]\((static/|uploads/|generated_images/)[^)]{1,200}\)'
)
_MARKDOWN_IMAGE_ANY = re.compile(r'!\[[^\]]{0,200}\]\(([^)]{1,200})\)')
_GENERATED_IMAGE_SRC = re.compile(r'src="(static/generated_images/[^"]+)"')

# Maximum length for regex input to prevent ReDoS
_REGEX_INPUT_LIMIT = 10000

# Maximum chars to buffer for multi-line command detection
_COMMAND_BUFFER_LIMIT = 16000


def _safe_regex_search(pattern: re.Pattern, text: str) -> re.Match | None:
    """Safely search with input length limit to prevent ReDoS."""
    if len(text) > _REGEX_INPUT_LIMIT:
        text = text[:_REGEX_INPUT_LIMIT]
    return pattern.search(text)


class StreamState(Enum):
    """StreamFilter state machine states."""
    NORMAL = auto()  # Yielding text immediately
    COMMAND_DETECTED = auto()  # Found '/' at line start, buffering
    COMMAND_EXECUTING = auto()  # Tool running


class StreamFilter:
    """Stateful filter with line-buffering for command detection.

    v3.1.0 refactor: line-buffering approach that preserves typing effect.

    Behavior:
      - Yield text immediately line-by-line
      - Buffer ONLY lines that START with '/'
      - On newline after '/': execute command, emit placeholder, continue
      - Handle multi-line arguments (quoted strings, JSON blocks)

    State Machine:
      NORMAL → COMMAND_DETECTED: when line starts with '/'
      COMMAND_DETECTED → COMMAND_EXECUTING: when newline received
      COMMAND_EXECUTING → NORMAL: after tool completes

    Usage:
        sf = StreamFilter()
        for chunk in upstream:
            for event in sf.feed(chunk):
                if isinstance(event, str):
                    yield event  # text chunk
                elif isinstance(event, dict):
                    # {"type": "command_detected", "command": {...}}
                    # {"type": "tool_result", "result": {...}}
                    yield event
        for event in sf.flush():
            yield event

        # After streaming completes:
        if sf.command:
            ...  # command was executed
        full_text = sf.full_text
    """

    __slots__ = (
        "_state",
        "_buffer",
        "_line_buffer",
        "command",
        "full_text",
        "tool_result",
    )

    def __init__(self) -> None:
        self._state = StreamState.NORMAL
        self._buffer = ""
        self._line_buffer = ""
        self.command: dict[str, Any] | None = None
        self.full_text = ""
        self.tool_result: dict[str, Any] | None = None

    def feed(self, chunk: str) -> Iterator[str | dict]:
        if not chunk:
            return
        self.full_text += chunk

        # Process chunk character by character for line detection
        for char in chunk:
            if self._state == StreamState.NORMAL:
                # In normal mode, yield immediately unless we see '/' at line start
                if char == "/" and not self._line_buffer.strip():
                    # Potential command at line start
                    self._state = StreamState.COMMAND_DETECTED
                    self._line_buffer += char
                else:
                    self._line_buffer += char
                    # Always yield character immediately (typing effect)
                    yield char
                    # Clear line buffer after newline
                    if char == "\n":
                        self._line_buffer = ""

            elif self._state == StreamState.COMMAND_DETECTED:
                self._line_buffer += char
                self._buffer += char

                if char == "\n":
                    # End of command line - parse and execute
                    self._execute_command()
                    self._state = StreamState.NORMAL
                    self._buffer = ""
                    self._line_buffer = ""

                elif len(self._buffer) >= _COMMAND_BUFFER_LIMIT:
                    # Buffer overflow - treat as plain text
                    yield self._line_buffer
                    self._state = StreamState.NORMAL
                    self._buffer = ""
                    self._line_buffer = ""

            elif self._state == StreamState.COMMAND_EXECUTING:
                # Tool is running - buffer incoming text
                self._line_buffer += char

    def _execute_command(self) -> None:
        """Parse and execute the buffered command line."""
        command_line = "/" + self._buffer.rstrip("\n")
        parsed = parse_command_with_multiline_args(command_line)

        if parsed and parsed.get("command"):
            self.command = parsed
            # Execute the tool
            tool_name, result = execute_command(parsed)
            self.tool_result = {
                "tool": tool_name,
                "result": result,
            }
        else:
            # Not a valid command - treat as plain text
            self._line_buffer = command_line + "\n"

    def flush(self) -> Iterator[str | dict]:
        """Drain any held-back text. Call once after upstream completes."""
        if self._state == StreamState.COMMAND_DETECTED and self._buffer:
            # Stream ended mid-command - try to execute
            self._execute_command()
            self._state = StreamState.NORMAL
            self._buffer = ""

        if self._line_buffer:
            yield self._line_buffer
            self._line_buffer = ""


# --------------------------------------------------------------------
# Multi-line Argument Parsing (v3.1.0)
# --------------------------------------------------------------------

# Regex patterns for argument parsing
_RX_QUOTED_STRING = re.compile(
    r'(\w+)="((?:[^"\\]|\\.)*)"\s*', re.DOTALL
)
_RX_JSON_BLOCK = re.compile(r"^\s*\{[\s\S]*\}\s*$", re.DOTALL)


def parse_command_with_multiline_args(
    command_line: str,
    following_lines: list[str] | None = None,
) -> dict[str, Any] | None:
    """Parse command including multi-line arguments.

    Supports:
    - Single positional argument: /imagine cute cat
    - Named args: /memory_store fact="value" category="Identity"
    - Multi-line quoted strings: fact="line1
                                  line2"
    - JSON blocks after newline: /request POST url
                                 {"key": "value"}

    Returns:
        {"command": str, "args": dict, "full_command": str}
        or None if not a valid command.
    """
    if not command_line or not command_line.strip():
        return None

    # Get first line (command + potential args)
    lines = command_line.strip().split("\n")
    first_line = lines[0]
    rest_lines = lines[1:] if len(lines) > 1 else (following_lines or [])

    if not first_line.startswith("/"):
        return None

    # Parse command name and initial args
    parts = first_line.split(None, 1)
    command_name = parts[0][1:]  # strip leading /
    args_str = parts[1] if len(parts) > 1 else ""

    args: dict[str, Any] = {}

    # Check for JSON block in remaining lines
    if rest_lines:
        rest_text = "\n".join(rest_lines).strip()
        if _RX_JSON_BLOCK.match(rest_text):
            try:
                json_data = json.loads(rest_text)
                if isinstance(json_data, dict):
                    args.update(json_data)
                else:
                    args["json_payload"] = json_data
                rest_text = ""
            except json.JSONDecodeError:
                pass

        # If no JSON, treat as positional continuation
        if rest_text and not args:
            args_str = args_str + " " + rest_text if args_str else rest_text

    # Parse named args from args_str (quoted strings)
    if args_str:
        # Try to extract quoted args
        remaining = args_str
        while True:
            match = _RX_QUOTED_STRING.match(remaining)
            if match:
                key, value = match.group(1), match.group(2)
                # Unescape
                value = value.replace('\\"', '"').replace("\\\\", "\\")
                args[key] = value
                remaining = remaining[match.end() :]
                continue
            break

        # If no named args found, treat as positional
        if not args and remaining.strip():
            positional = remaining.strip()
            # Remove surrounding quotes if present
            if len(positional) >= 2 and positional[0] == '"' == positional[-1]:
                positional = positional[1:-1]
            # Map to tool-specific key
            tool_key = _STRING_ARG_TOOLS.get(command_name, "query")
            args[tool_key] = positional

    return {
        "command": command_name,
        "args": args,
        "full_command": command_line.strip(),
    }


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
    # Limit input length to prevent ReDoS
    if len(response_text) > _REGEX_INPUT_LIMIT:
        response_text = response_text[:_REGEX_INPUT_LIMIT]
    return bool(_MARKDOWN_IMAGE_PATH.search(response_text))


def extract_markdown_image_path(response_text: str) -> str | None:
    """Return the first markdown image path/URL in *response_text*, if any."""
    # Limit input length to prevent ReDoS
    if len(response_text) > _REGEX_INPUT_LIMIT:
        response_text = response_text[:_REGEX_INPUT_LIMIT]
    match = _MARKDOWN_IMAGE_ANY.search(response_text)
    return match.group(1) if match else None


IMAGE_SHORTCUT_WARNING = (
    "\n\nImage output detected via incorrect method. "
    "Please use /imagine to generate images."
)
