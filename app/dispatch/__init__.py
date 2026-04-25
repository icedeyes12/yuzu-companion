# FILE: app/dispatch/__init__.py
# DESCRIPTION: Hybrid tool dispatch package
#              Routes tool calls to local or MCP execution

from app.dispatch.hybrid import (
    HybridDispatcher,
    dispatch_tool,
    get_dispatcher,
    discover_all_tools,
)

__all__ = [
    "HybridDispatcher",
    "dispatch_tool",
    "get_dispatcher",
    "discover_all_tools",
]
