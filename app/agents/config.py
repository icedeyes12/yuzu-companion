# FILE: app/agents/config.py
# DESCRIPTION: Agentic loop configuration
#              Tune iteration limits, timeouts, and behavior

from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Configuration for agentic loop behavior.
    
    These values control the Plan-Execute-Observe cycle.
    """
    
    # Loop limits
    max_iterations: int = 50
    """Maximum tool-calling iterations before forcing a response."""
    
    total_timeout_seconds: int = 1800
    """Total time budget for a single user message (30 min)."""
    
    tool_timeout_seconds: int = 60
    """Per-tool execution timeout."""
    
    # Dispatch behavior
    prefer_local_tools: bool = True
    """Try local tools first, fall back to MCP if not found."""
    
    enable_mcp: bool = True
    """Enable MCP remote tool access."""
    
    mcp_endpoint: str = "https://api.zo.computer/mcp"
    """MCP server endpoint."""
    
    # Thought capture
    enable_thought_capture: bool = True
    """Parse and log <thought> blocks from LLM responses."""
    
    # Synthesis behavior
    auto_synthesis: bool = True
    """Run synthesis pass after tool execution to narrate results."""
    
    synthesis_max_tokens: int = 500
    """Token budget for synthesis pass."""
    
    # Command detection
    command_patterns: tuple[str, ...] = ("bracket", "slash")
    """Which command formats to detect. Order = priority."""
    
    @property
    def total_timeout_minutes(self) -> float:
        return self.total_timeout_seconds / 60.0


# Default singleton
DEFAULT_CONFIG = AgentConfig()


def get_agent_config() -> AgentConfig:
    """Get the current agent configuration.
    
    In the future, this could read from DB or env vars.
    For now, returns the default.
    """
    return DEFAULT_CONFIG


def update_agent_config(**kwargs) -> AgentConfig:
    """Update agent configuration at runtime.
    
    Returns a new config object; does not mutate the default.
    """
    current = get_agent_config()
    updates = {k: v for k, v in kwargs.items() if hasattr(current, k)}
    return AgentConfig(**{**current.__dict__, **updates})
