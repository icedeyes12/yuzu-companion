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

# Maximum chars to buffer while sniffing for a leading /command.
# Generous enough for any realistic command line, but bounded so we never
# starve the user of streamed output if the model omits a newline.
_COMMAND_SNIFF_LIMIT = 512

# Maximum length for regex input to prevent ReDoS
_REGEX_INPUT_LIMIT = 10000

# Maximum chars to buffer for <tools> block detection
_TOOLS_BLOCK_LIMIT = 5000


def _safe_regex_search(pattern: re.Pattern, text: str) -> re.Match | None:
    """Safely search with input length limit to prevent ReDoS."""
    if len(text) > _REGEX_INPUT_LIMIT:
        text = text[:_REGEX_INPUT_LIMIT]
    return pattern.search(text)


# ------------------------------------------------
# v3.1.0: StreamState for XML <tools> detection
# ------------------------------------------------

class StreamState(Enum):
    """State machine states for StreamFilter v3.1.0."""
    NORMAL = auto()           # Yielding text immediately
    COMMAND_SNIFFING = auto() # Buffering to detect leading /command
    TOOLS_DETECTED = auto()   # Buffering <tools> block
    TOOLS_COMPLETE = auto()   # <tools> block parsed, ready to emit


# ------------------------------------------------
# v3.1.0: XML Parsing Patterns
# ------------------------------------------------

# Pattern to match complete <tools>...</tools> block
_TOOLS_BLOCK_PATTERN = re.compile(
    r'<tools>\s*'
    r'<name>([^<]+)</name>\s*'
    r'(?:<args>(.*?)</args>\s*)?'
    r'</tools>',
    re.DOTALL
)

# Pattern to extract individual args from <args> block
_ARG_PATTERN = re.compile(r'<(\w+)>([^<]*)</\1>')


def _parse_tools_block(block: str) -> dict[str, Any] | None:
    """Parse <tools> block into {name, args} dict.
    
    Args:
        block: The <tools>...</tools> XML block
        
    Returns:
        {"name": str, "args": dict} or None if parsing fails
    """
    match = _TOOLS_BLOCK_PATTERN.search(block)
    if not match:
        return None
    
    tool_name = match.group(1).strip()
    args_str = match.group(2)
    
    args = {}
    if args_str:
        # Parse individual <key>value</key> args
        for arg_match in _ARG_PATTERN.finditer(args_str):
            key = arg_match.group(1)
            value = arg_match.group(2)
            args[key] = value
    
    return {"name": tool_name, "args": args}


class StreamFilter:
    """Stateful filter for v3.1.0 universal inline command flow.
    
    Two detection modes:
    1. Legacy: Leading /command on first line (backward compat)
    2. v3.1.0: <tools> XML block anywhere in stream
    
    Emits placeholder events when <tools> block is detected.
    
    Behavior:
    - Normal text yields immediately (except last 6 chars for <tools> detection)
    - When <tools> detected: buffer until </tools>, emit placeholder
    - After tools complete: yield remaining text immediately
    
    Usage:
        sf = StreamFilter()
        for chunk in upstream:
            for output in sf.feed(chunk):
                if isinstance(output, dict):
                    # Placeholder event: {"type": "tool_executing", ...}
                    yield output
                else:
                    # Text chunk
                    yield output
        
        for output in sf.flush():
            yield output
        
        # After streaming:
        if sf.tool_call:
            name = sf.tool_call["name"]
            args = sf.tool_call["args"]
    """
    
    __slots__ = (
        "_buffer",
        "_state",
        "_command_decided",
        "_is_command",
        "command",      # Legacy: /command detection result
        "tool_call",    # v3.1.0: <tools> block parsed result
        "full_text",
        "_yielded_placeholder",
    )
    
    def __init__(self) -> None:
        self._buffer = ""
        self._state = StreamState.NORMAL
        self._command_decided = False
        self._is_command = False
        self.command: dict[str, str] | None = None
        self.tool_call: dict[str, Any] | None = None
        self.full_text = ""
        self._yielded_placeholder = False
    
    def feed(self, chunk: str) -> Iterator[str | dict[str, Any]]:  # type: ignore[name-defined]
        """Process a chunk and yield text or placeholder events.
        
        Yields:
            str: Text to display (narrative before/after tools)
            dict: Placeholder event {"type": "tool_executing", "name": ..., "args": ...}
        """
        if not chunk:
            return
        
        self.full_text += chunk
        
        # Process character by character
        for char in chunk:
            self._buffer += char
            
            if self._state == StreamState.NORMAL:
                # Check for <tools> start
                if self._buffer.endswith("<tools>"):
                    self._state = StreamState.TOOLS_DETECTED
                    
                    # Yield text before <tools>
                    text_before = self._buffer[:-7]
                    if text_before:
                        yield text_before
                    
                    # Check for legacy /command in text before tools
                    if not self._command_decided and text_before.strip():
                        lines = text_before.split("\n")
                        if lines and lines[0].strip().startswith("/"):
                            self.command = detect_command(lines[0])
                            if self.command:
                                self._is_command = True
                        self._command_decided = True
                    
                    self._buffer = "<tools>"
                
                # Legacy /command backward compat: buffer if starts with /
                elif not self._command_decided and self._buffer.strip().startswith("/"):
                    # Could be a legacy command - buffer until newline
                    if "\n" in self._buffer:
                        # First line complete - check if command
                        first_line = self._buffer.split("\n")[0]
                        self.command = detect_command(first_line)
                        if self.command:
                            self._is_command = True
                            self._command_decided = True
                            # Clear buffer (command line consumed)
                            idx = self._buffer.find("\n") + 1
                            self._buffer = self._buffer[idx:]
                        else:
                            # Not a valid command - yield buffer
                            self._command_decided = True
                            yield self._buffer
                            self._buffer = ""
                
                # Yield normal text, but keep last 6 chars for "<tools>" detection
                elif len(self._buffer) > 6 and not self._buffer.endswith("<"):
                    # Safe to yield everything except last 6 chars
                    safe_len = len(self._buffer) - 6
                    yield self._buffer[:safe_len]
                    self._buffer = self._buffer[safe_len:]
            
            elif self._state == StreamState.TOOLS_DETECTED:
                # Check for </tools> end
                if self._buffer.endswith("</tools>"):
                    self._state = StreamState.TOOLS_COMPLETE
                    
                    # Parse the tools block
                    self.tool_call = _parse_tools_block(self._buffer)
                    
                    if self.tool_call and not self._yielded_placeholder:
                        yield {
                            "type": "tool_executing",
                            "name": self.tool_call["name"],
                            "args": self.tool_call["args"],
                        }
                        self._yielded_placeholder = True
                    
                    self._buffer = ""
            
            elif self._state == StreamState.TOOLS_COMPLETE:
                # Yield text after tools block immediately
                yield char
    
    def flush(self) -> Iterator[str | dict[str, Any]]:  # type: ignore[name-defined]
        """Drain any held-back text. Call once after upstream completes.
        
        Handles incomplete <tools> block gracefully.
        """
        if self._buffer:
            if self._state == StreamState.TOOLS_DETECTED:
                # Incomplete tools block - yield as text
                log.warning("Incomplete <tools> block detected, yielding as text")
            
            # Check for legacy /command in remaining buffer
            if not self._command_decided:
                # Check if FULL TEXT starts with / (legacy command)
                # We use full_text because buffer may be partial from chunked yielding
                stripped = self.full_text.strip()
                if stripped.startswith("/"):
                    # It's a command - detect and don't yield
                    self.command = detect_command(self.full_text)
                    if self.command:
                        self._is_command = True
                        self._command_decided = True
                        self._buffer = ""
                        return  # Don't yield the command
            
            yield self._buffer
            self._buffer = ""


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
