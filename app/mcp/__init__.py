# FILE: app/mcp/__init__.py
# DESCRIPTION: MCP (Model Context Protocol) client package
#              Bridges Yuzu to Zo's sandboxed tool ecosystem

from app.mcp.client import (
    MCPClient,
    MCPTool,
    get_mcp_client,
    discover_mcp_tools,
)

__all__ = [
    "MCPClient",
    "MCPTool",
    "get_mcp_client",
    "discover_mcp_tools",
]
