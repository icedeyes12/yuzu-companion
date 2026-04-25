from __future__ import annotations

# Re-export from app.providers for convenience imports
from app.providers import get_ai_manager, reload_ai_manager

# Re-export agentic components
from app.orchestrator_agentic import (
    run_agentic_loop,
    stream_agentic_loop,
    get_agentic_orchestrator,
    TurnResult,
)

from app.agents import (
    AgentConfig,
    get_agent_config,
    ToolCall,
    ThoughtBlock,
    parse_command,
    parse_thought,
)

from app.dispatch import (
    HybridDispatcher,
    dispatch_tool,
    discover_all_tools,
)

__all__ = [
    # Providers
    "get_ai_manager",
    "reload_ai_manager",
    # Agentic loop
    "run_agentic_loop",
    "stream_agentic_loop",
    "get_agentic_orchestrator",
    "TurnResult",
    # Agents
    "AgentConfig",
    "get_agent_config",
    "ToolCall",
    "ThoughtBlock",
    "parse_command",
    "parse_thought",
    # Dispatch
    "HybridDispatcher",
    "dispatch_tool",
    "discover_all_tools",
]
