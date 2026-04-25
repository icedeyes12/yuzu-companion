# FILE: app/agents/__init__.py
# DESCRIPTION: Agentic loop components package
#              Plan-Execute-Observe architecture for autonomous tool use

from app.agents.thought_parser import (
    ThoughtBlock,
    parse_thought,
    extract_thought_and_response,
    strip_thought_blocks,
)

from app.agents.command_parser import (
    ToolCall,
    parse_command,
    parse_bracket_command,
    parse_slash_command,
    strip_command,
)

from app.agents.stream_parser import (
    AgenticStreamParser,
    StreamMeta,
    create_stream_parser,
    parse_streaming_response,
)

from app.agents.config import (
    AgentConfig,
    get_agent_config,
    update_agent_config,
    DEFAULT_CONFIG,
)

__all__ = [
    # Thought parser
    "ThoughtBlock",
    "parse_thought",
    "extract_thought_and_response",
    "strip_thought_blocks",
    # Command parser
    "ToolCall",
    "parse_command",
    "parse_bracket_command",
    "parse_slash_command",
    "strip_command",
    # Stream parser
    "AgenticStreamParser",
    "StreamMeta",
    "create_stream_parser",
    "parse_streaming_response",
    # Config
    "AgentConfig",
    "get_agent_config",
    "update_agent_config",
    "DEFAULT_CONFIG",
]
