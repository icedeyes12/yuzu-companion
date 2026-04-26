# FILE: app/agents/command_parser.py
# DESCRIPTION: Parse [COMMAND: tool_name(args)] patterns from LLM responses
#              Hybrid format supporting both legacy /command and new bracket syntax
#
# Supported formats:
#   Legacy: /imagine a cat
#   New:    [COMMAND: imagine(prompt="a cat")]
#   New:    [COMMAND: zo_search(query="what is rust")]
#
# The parser normalizes both to a common ToolCall structure.

from __future__ import annotations

import re
import json
from dataclasses import dataclass
from typing import Any

# Bracket-style command: [COMMAND: tool_name(args)]
_BRACKET_COMMAND_PATTERN = re.compile(
    r"\[COMMAND:\s*"          # [COMMAND:
    r"(\w+)"                  # tool_name
    r"\s*"                    # optional whitespace
    r"(?:\(([^)]*)\))?"       # optional (args) - capture inside parens
    r"\s*\]",                 # closing ]
    re.IGNORECASE,
)

# Legacy slash command: /tool_name args
_SLASH_COMMAND_PATTERN = re.compile(
    r"^/(\w+)\s*(.*)$",
    re.MULTILINE,
)

# Note: Tool aliases for normalization are defined in app/commands._TOOL_ALIASES
# and applied in orchestrator._execute_bracket_command and commands.execute_command.


@dataclass
class ToolCall:
    """Parsed tool call from LLM response."""
    tool_name: str
    arguments: dict[str, Any]
    raw_text: str = ""
    format_type: str = "unknown"  # "bracket" | "slash"
    id: str = ""  # Unique ID for tool call tracking
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for API responses."""
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "format_type": self.format_type,
            "id": self.id,
        }


def _parse_bracket_args(args_str: str | None) -> dict[str, Any]:
    """Parse bracket-style arguments: key="value", key=123"""
    if not args_str:
        return {}
    
    result: dict[str, Any] = {}
    
    # Try JSON parse first
    try:
        # Wrap in braces to make it a JSON object
        json_str = "{" + args_str + "}"
        # Convert key=value to key:value for JSON
        # This is a simplified approach; complex nested values may fail
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    
    # Fallback: parse key=value pairs
    # Pattern: key="value" or key=value or key='value'
    pair_pattern = re.compile(
        r'(\w+)\s*=\s*["\']?([^"\',\)]+)["\']?',
    )
    
    for match in pair_pattern.finditer(args_str):
        key, value = match.groups()
        # Try to convert to appropriate type
        value = value.strip()
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        elif value.isdigit():
            value = int(value)
        elif re.match(r"^-?\d+\.\d+$", value):
            value = float(value)
        result[key] = value
    
    return result


def parse_bracket_command(text: str) -> ToolCall | None:
    """Parse a [COMMAND: ...] pattern from text.
    
    Returns None if no bracket command found.
    """
    match = _BRACKET_COMMAND_PATTERN.search(text)
    if not match:
        return None
    
    tool_name = match.group(1)
    args_str = match.group(2)
    raw_text = match.group(0)
    
    arguments = _parse_bracket_args(args_str)
    
    return ToolCall(
        tool_name=tool_name,
        arguments=arguments,
        raw_text=raw_text,
        format_type="bracket",
    )


def parse_slash_command(text: str) -> ToolCall | None:
    """Parse a legacy /command from text.
    
    Returns None if no slash command found.
    """
    # Find first line that starts with /
    for line in text.split("\n"):
        line = line.strip()
        match = _SLASH_COMMAND_PATTERN.match(line)
        if match:
            tool_name = match.group(1)
            args_str = match.group(2)
            
            # For single-string-arg tools, wrap the raw string
            if tool_name in ("imagine", "request", "memory_store"):
                arg_key = {
                    "imagine": "prompt",
                    "request": "url",
                    "memory_store": "fact",
                }.get(tool_name, "query")
                arguments = {arg_key: args_str}
            else:
                # Try JSON parse for complex args
                try:
                    arguments = json.loads(args_str)
                    if not isinstance(arguments, dict):
                        arguments = {"query": args_str}
                except json.JSONDecodeError:
                    arguments = {"query": args_str}
            
            return ToolCall(
                tool_name=tool_name,
                arguments=arguments,
                raw_text=line,
                format_type="slash",
            )
    
    return None


def parse_command(text: str) -> ToolCall | None:
    """Parse command from text using either format.
    
    Priority:
      1. [COMMAND: ...] bracket format (new, preferred)
      2. /command slash format (legacy, fallback)
    
    Returns the first matching command or None.
    """
    # Try bracket format first
    bracket = parse_bracket_command(text)
    if bracket:
        return bracket
    
    # Fall back to slash format
    return parse_slash_command(text)


def strip_command(text: str, tool_call: ToolCall | None = None) -> str:
    """Remove the command portion from text, leaving the rest.
    
    If tool_call is not provided, attempts to parse one from the text.
    """
    if tool_call is None:
        tool_call = parse_command(text)
        if tool_call is None:
            return text  # No command to strip
    
    if tool_call.format_type == "bracket":
        return text.replace(tool_call.raw_text, "").strip()
    else:
        # For slash commands, remove the first line
        lines = text.split("\n")
        return "\n".join(
            line for line in lines 
            if line.strip() != tool_call.raw_text
        ).strip()
