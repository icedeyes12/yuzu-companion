# FILE: app/agents/stream_parser.py
# DESCRIPTION: Buffer-based streaming parser for agentic loop
#              Handles split chunks for [COMMAND: ...] and <thought>...</thought>
#
# Problem:
#   LLM streaming can split patterns across chunks:
#     Chunk 1: "[COMMAND: imag"
#     Chunk 2: "ine(prompt='a cat')]"
#   
#   Naive parsing would miss the command.
#
# Solution:
#   Buffer chunks until we see complete patterns:
#   - [COMMAND: ...] with balanced parentheses
#   - <thought>...</thought> with matching tags
#
# Architecture:
#   ┌─────────────────────────────────────────┐
#   │         AgenticStreamParser             │
#   │  ┌─────────────────────────────────┐    │
#   │  │ Buffer (grows until decision)   │    │
#   │  │  - Scan for complete patterns   │    │
#   │  │  - Yield safe text + metadata   │    │
#   │  └─────────────────────────────────┘    │
#   │                                         │
#   │  Output: (chunk, metadata) tuples       │
#   │    metadata = {                         │
#   │      "thought": ThoughtBlock | None,    │
#   │      "command": ToolCall | None,        │
#   │      "is_complete": bool,               │
#   │    }                                    │
#   └─────────────────────────────────────────┘

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from app.agents.command_parser import ToolCall, parse_bracket_command
from app.agents.thought_parser import ThoughtBlock, parse_thought

log = __import__("logging").getLogger(__name__)

# Buffer limits
_MAX_BUFFER = 8192  # Max chars to buffer before forcing flush
_COMMAND_PREFIX = "[COMMAND:"
_THOUGHT_OPEN = "<thought>"
_THOUGHT_CLOSE = "</thought>"


@dataclass
class StreamMeta:
    """Metadata emitted with each safe chunk."""
    thought: ThoughtBlock | None = None
    command: ToolCall | None = None
    is_complete: bool = False  # True when full response parsed


@dataclass
class ParsedPattern:
    """A parsed pattern found in buffer."""
    pattern_type: str  # "command" | "thought" | "text"
    start: int
    end: int
    content: str
    parsed: ToolCall | ThoughtBlock | str | None = None


class AgenticStreamParser:
    """Stateful buffer-based parser for streaming LLM responses.
    
    Handles:
      - [COMMAND: tool(args)] split across chunks
      - <thought>...</thought> split across chunks
      - Multiple commands in single response
      - Mixed text + commands + thoughts
    
    Usage:
        parser = AgenticStreamParser()
        
        for chunk in llm_stream():
            for safe_chunk, meta in parser.feed(chunk):
                if meta.command:
                    # Execute command, don't render yet
                    execute_command(meta.command)
                else:
                    # Safe to render
                    yield safe_chunk
        
        # Final flush
        for safe_chunk, meta in parser.flush():
            yield safe_chunk
        
        # Access full parsed state
        result = parser.result  # TurnResult-like
    """
    
    __slots__ = (
        "_buffer",
        "_emitted",
        "_patterns",
        "full_text",
        "thoughts",
        "commands",
        "result",
    )
    
    def __init__(self) -> None:
        self._buffer = ""
        self._emitted = 0  # chars already yielded
        self._patterns: list[ParsedPattern] = []
        
        # Final state (populated after flush)
        self.full_text = ""
        self.thoughts: list[ThoughtBlock] = []
        self.commands: list[ToolCall] = []
        self.result: dict[str, Any] | None = None
    
    def feed(self, chunk: str) -> Iterator[tuple[str, StreamMeta]]:
        """Process a chunk, yield safe text + metadata.
        
        Guarantees:
          - Yields only text that won't be re-parsed later
          - Commands are yielded with metadata (suppressed from text)
          - Thoughts are stripped from text, yielded in metadata
        """
        if not chunk:
            return
        
        self._buffer += chunk
        self.full_text += chunk
        
        # Scan for complete patterns
        self._scan_patterns()
        
        # Yield safe text up to next pattern boundary
        yield from self._emit_safe()
    
    def flush(self) -> Iterator[tuple[str, StreamMeta]]:
        """Drain remaining buffer after stream ends.
        
        Handles:
          - Incomplete patterns (treated as text)
          - Final text after last pattern
        """
        # Final scan for any remaining complete patterns
        self._scan_patterns()
        
        # Emit any remaining safe text
        yield from self._emit_safe()
        
        # Handle incomplete patterns in buffer
        if len(self._buffer) > self._emitted:
            remaining = self._buffer[self._emitted:]
            
            # Try to parse incomplete bracket command
            incomplete_cmd = self._try_parse_incomplete_command(remaining)
            
            if incomplete_cmd:
                # Emit as command, not text
                meta = StreamMeta(command=incomplete_cmd, is_complete=True)
                yield ("", meta)
                self.commands.append(incomplete_cmd)
            else:
                # Emit as plain text
                meta = StreamMeta(is_complete=True)
                yield (remaining, meta)
        
        # Build final result
        self.result = {
            "full_text": self.full_text,
            "thoughts": self.thoughts,
            "commands": self.commands,
        }
    
    def _scan_patterns(self) -> None:
        """Scan buffer for complete patterns."""
        # Limit buffer size to prevent memory issues
        if len(self._buffer) > _MAX_BUFFER:
            # Force flush oldest text
            self._emit_safe()
        
        # Scan for [COMMAND: ...] patterns
        self._scan_commands()
        
        # Scan for <thought>...</thought> patterns
        self._scan_thoughts()
    
    def _scan_commands(self) -> None:
        """Find complete [COMMAND: ...] patterns in buffer."""
        # Find all [COMMAND: occurrences
        pos = self._emitted
        while pos < len(self._buffer):
            start = self._buffer.find(_COMMAND_PREFIX, pos)
            if start == -1:
                break
            
            # Find matching ] with balanced parens
            end = self._find_bracket_end(start)
            if end == -1:
                # Incomplete command, wait for more chunks
                break
            
            # Extract and parse
            cmd_text = self._buffer[start:end + 1]
            tool_call = parse_bracket_command(cmd_text)
            
            if tool_call:
                self._patterns.append(ParsedPattern(
                    pattern_type="command",
                    start=start,
                    end=end + 1,
                    content=cmd_text,
                    parsed=tool_call,
                ))
                self.commands.append(tool_call)
            
            pos = end + 1
    
    def _scan_thoughts(self) -> None:
        """Find complete <thought>...</thought> patterns in buffer."""
        pos = self._emitted
        while pos < len(self._buffer):
            start = self._buffer.find(_THOUGHT_OPEN, pos)
            if start == -1:
                break
            
            end = self._buffer.find(_THOUGHT_CLOSE, start)
            if end == -1:
                # Incomplete thought, wait for more chunks
                break
            
            # Extract and parse (include closing tag)
            thought_text = self._buffer[start:end + len(_THOUGHT_CLOSE)]
            thought_block = parse_thought(thought_text)
            
            if thought_block:
                self._patterns.append(ParsedPattern(
                    pattern_type="thought",
                    start=start,
                    end=end + len(_THOUGHT_CLOSE),
                    content=thought_text,
                    parsed=thought_block,
                ))
                self.thoughts.append(thought_block)
            
            pos = end + len(_THOUGHT_CLOSE)
    
    def _find_bracket_end(self, start: int) -> int:
        """Find the closing ] for a [COMMAND: starting at start.
        
        Handles nested parentheses:
          [COMMAND: request(url="https://api.example.com", method="GET")]
        
        Returns -1 if not found (incomplete).
        """
        if start + len(_COMMAND_PREFIX) >= len(self._buffer):
            return -1
        
        pos = start + len(_COMMAND_PREFIX)
        paren_depth = 0
        found_open_paren = False
        
        while pos < len(self._buffer):
            char = self._buffer[pos]
            
            if char == "(":
                paren_depth += 1
                found_open_paren = True
            elif char == ")":
                paren_depth -= 1
                if paren_depth < 0:
                    # Unbalanced parens, malformed command
                    return -1
            elif char == "]" and (paren_depth == 0 or not found_open_paren):
                # Found closing bracket with balanced parens
                # OR command with no args: [COMMAND: imagine()]
                return pos
            
            pos += 1
        
        # Incomplete
        return -1
    
    def _emit_safe(self) -> Iterator[tuple[str, StreamMeta]]:
        """Yield safe text between patterns.
        
        "Safe" = text that won't be re-parsed as part of a pattern.
        """
        if not self._patterns:
            # No patterns yet, but check if we can emit safe prefix
            # Text is safe if it doesn't start with a pattern prefix
            if self._buffer and not self._buffer[self._emitted:].lstrip().startswith((_COMMAND_PREFIX, _THOUGHT_OPEN)):
                # Find where pattern might start
                for prefix in (_COMMAND_PREFIX, _THOUGHT_OPEN):
                    pos = self._buffer.find(prefix, self._emitted)
                    if pos > self._emitted:
                        # Emit text before the pattern start
                        safe_text = self._buffer[self._emitted:pos]
                        if safe_text:
                            yield (safe_text, StreamMeta())
                        return
            return
        
        # Sort patterns by position
        sorted_patterns = sorted(self._patterns, key=lambda p: p.start)
        
        # Find the first complete pattern we haven't processed
        for pattern in sorted_patterns:
            if pattern.end <= self._emitted:
                # Already processed
                continue
            
            # Emit text before the pattern
            if pattern.start > self._emitted:
                safe_text = self._buffer[self._emitted:pattern.start]
                if safe_text:
                    meta = StreamMeta()
                    yield (safe_text, meta)
            
            # Emit pattern metadata (with empty text)
            if pattern.pattern_type == "command":
                meta = StreamMeta(command=pattern.parsed)
                yield ("", meta)
            elif pattern.pattern_type == "thought":
                meta = StreamMeta(thought=pattern.parsed)
                yield ("", meta)
            
            self._emitted = pattern.end
        
        # After processing all patterns, emit trailing text
        if self._emitted < len(self._buffer):
            # Check if trailing text might be start of new pattern
            remaining = self._buffer[self._emitted:]
            if remaining and not remaining.lstrip().startswith((_COMMAND_PREFIX, _THOUGHT_OPEN)):
                safe_text = remaining
                meta = StreamMeta()
                self._emitted = len(self._buffer)
                yield (safe_text, meta)
    
    def _try_parse_incomplete_command(self, text: str) -> ToolCall | None:
        """Try to parse an incomplete [COMMAND: ... at stream end.
        
        Handles cases where stream ends mid-command:
          "[COMMAND: imagine(prompt='a cat"
        
        Attempts graceful extraction.
        """
        # Check if it starts with [COMMAND:
        if not text.strip().startswith(_COMMAND_PREFIX):
            return None
        
        # Try to parse anyway (might work if args are simple)
        # Add closing bracket and paren if missing
        test_text = text
        if not test_text.rstrip().endswith("]"):
            # Count unclosed parens
            open_parens = test_text.count("(") - test_text.count(")")
            test_text += ")" * max(open_parens, 0) + "]"
        
        return parse_bracket_command(test_text)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def create_stream_parser() -> AgenticStreamParser:
    """Factory for AgenticStreamParser."""
    return AgenticStreamParser()


def parse_streaming_response(
    chunks: Iterator[str],
) -> tuple[str, list[ToolCall], list[ThoughtBlock]]:
    """Parse a complete streaming response.
    
    Returns:
        (full_text, commands, thoughts)
    """
    parser = AgenticStreamParser()
    
    for chunk in chunks:
        list(parser.feed(chunk))  # Consume iterator
    
    list(parser.flush())
    
    return parser.full_text, parser.commands, parser.thoughts
