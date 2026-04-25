# FILE: app/agents/thought_parser.py
# DESCRIPTION: Parse <thought> blocks from LLM responses
#              Enables chain-of-thought capture for agentic reasoning
#
# Format:
#   <thought>
#   Planning: I need to search for X
#   Tools: zo_search, then summarize
#   </thought>
#   
#   [COMMAND: zo_search(query="...")]
#
# Parser extracts:
#   - thought_text: reasoning content
#   - planning: optional structured plan
#   - tools_mentioned: tool names extracted from thought

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_THOUGHT_PATTERN = re.compile(
    r"<thought>\s*(.*?)\s*</thought>",
    re.DOTALL | re.IGNORECASE,
)

_PLANNING_PATTERN = re.compile(
    r"planning:\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)

_TOOLS_PATTERN = re.compile(
    r"tools:\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)


@dataclass
class ThoughtBlock:
    """Parsed thought block from LLM response."""
    raw_text: str
    content: str = ""
    planning: str | None = None
    tools_mentioned: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "content": self.content,
            "planning": self.planning,
            "tools_mentioned": self.tools_mentioned,
        }


def parse_thought(response_text: str) -> ThoughtBlock | None:
    """Extract and parse a <thought> block from LLM response.
    
    Returns None if no thought block found.
    """
    match = _THOUGHT_PATTERN.search(response_text)
    if not match:
        return None
    
    raw_text = match.group(0)
    content = match.group(1).strip()
    
    # Extract planning section
    planning_match = _PLANNING_PATTERN.search(content)
    planning = planning_match.group(1).strip() if planning_match else None
    
    # Extract tools mentioned
    tools_match = _TOOLS_PATTERN.search(content)
    tools_mentioned: list[str] = []
    if tools_match:
        tools_str = tools_match.group(1).strip()
        # Split by comma or "then"
        tools_mentioned = [
            t.strip().rstrip(")")
            for t in re.split(r"[,\s]+then\s+|,|;", tools_str)
            if t.strip()
        ]
    
    return ThoughtBlock(
        raw_text=raw_text,
        content=content,
        planning=planning,
        tools_mentioned=tools_mentioned,
    )


def extract_thought_and_response(
    response_text: str,
) -> tuple[ThoughtBlock | None, str]:
    """Split response into thought block and remaining text.
    
    Returns:
        (thought_block, cleaned_response)
        - thought_block: None if no <thought> found
        - cleaned_response: Original text with <thought>...</thought> removed
    """
    thought = parse_thought(response_text)
    
    if thought is None:
        return None, response_text
    
    # Remove the thought block from response
    cleaned = _THOUGHT_PATTERN.sub("", response_text).strip()
    
    return thought, cleaned


def strip_thought_blocks(text: str) -> str:
    """Remove all <thought> blocks from text."""
    return _THOUGHT_PATTERN.sub("", text).strip()
