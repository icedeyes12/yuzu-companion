# FILE: app/dispatch/hybrid.py
# DESCRIPTION: Hybrid tool dispatcher — routes to local or MCP execution
#
# Architecture:
#   - Local tools: app/tools/registry.py (image_generate, request, memory_*)
#   - MCP tools:   app/mcp/client.py → Zo MCP Server (zo_search, zo_research, etc.)
#
# Priority:
#   1. If tool_name matches local tool → execute locally
#   2. Else if MCP available → execute via MCP client
#   3. Else → error with available tools list
#
# Tool Discovery:
#   - Local tools loaded lazily from registry
#   - MCP tools fetched at startup and cached

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    """Information about an available tool."""
    name: str
    description: str
    source: str  # "local" | "mcp"
    parameters: dict[str, Any] = field(default_factory=dict)
    is_terminal: bool = False  # Skip synthesis pass on success


class HybridDispatcher:
    """Dispatches tool calls to local or MCP execution.
    
    Usage:
        dispatcher = HybridDispatcher()
        result = await dispatcher.dispatch("zo_search", {"query": "hello"})
    """
    
    def __init__(self):
        self._local_tools: dict[str, ToolInfo] | None = None
        self._mcp_tools: dict[str, ToolInfo] | None = None
        self._mcp_available: bool = False
        self._initialized = False
    
    async def initialize(self) -> None:
        """Load local tools and discover MCP tools."""
        if self._initialized:
            return
        
        # Load local tools
        self._local_tools = self._load_local_tools()
        logger.info(f"[dispatch] Local tools loaded: {list(self._local_tools.keys())}")
        
        # Try to discover MCP tools
        try:
            from app.mcp import get_mcp_client
            client = get_mcp_client()
            if client and client.token:  # Sync check for token presence
                mcp_tools = await client.discover_tools()
                self._mcp_tools = {
                    t.name: ToolInfo(
                        name=t.name,
                        description=t.description,
                        source="mcp",
                        parameters=t.parameters,
                    )
                    for t in mcp_tools
                }
                self._mcp_available = True
                logger.info(f"[dispatch] MCP tools discovered: {list(self._mcp_tools.keys())}")
        except Exception as e:
            logger.warning(f"[dispatch] MCP discovery failed: {e}")
            self._mcp_tools = {}
            self._mcp_available = False
        
        self._initialized = True
    
    def _load_local_tools(self) -> dict[str, ToolInfo]:
        """Load tool definitions from local registry."""
        tools = {}
        try:
            from app.tools.registry import get_tool_definitions
            
            for tool_def in get_tool_definitions():
                params = {}
                for p in tool_def.parameters:
                    params[p.name] = {
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                    }
                
                tools[tool_def.name] = ToolInfo(
                    name=tool_def.name,
                    description=tool_def.description,
                    source="local",
                    parameters=params,
                    is_terminal=tool_def.is_terminal,
                )
                
                # Add aliases (e.g., "imagine" -> "image_generate")
                if tool_def.name == "image_generate":
                    tools["imagine"] = tools["image_generate"]
                elif tool_def.name == "http_request":
                    tools["request"] = tools["http_request"]
        
        except Exception as e:
            logger.warning(f"[dispatch] Failed to load local tools: {e}")
        
        return tools
    
    def get_all_tools(self) -> list[ToolInfo]:
        """Return all available tools (local + MCP)."""
        if not self._initialized:
            # Sync fallback for non-async contexts
            self._local_tools = self._load_local_tools()
            self._mcp_tools = {}
            self._initialized = True
        
        all_tools = {}
        # Local tools take priority (overwrite MCP if conflict)
        if self._mcp_tools:
            all_tools.update(self._mcp_tools)
        if self._local_tools:
            all_tools.update(self._local_tools)
        
        return list(all_tools.values())
    
    def get_tool_schemas(self) -> list[dict]:
        """Return tool schemas for LLM tools[] array."""
        schemas = []
        seen = set()
        
        for tool in self.get_all_tools():
            if tool.name in seen:
                continue
            seen.add(tool.name)
            
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": [
                            name for name, p in tool.parameters.items()
                            if p.get("required", True)
                        ],
                    },
                },
            })
        
        return schemas
    
    def is_local_tool(self, tool_name: str) -> bool:
        """Check if tool is a local tool."""
        if not self._initialized:
            self._local_tools = self._load_local_tools()
        return tool_name in (self._local_tools or {})
    
    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if tool is an MCP tool."""
        return (
            self._mcp_available
            and tool_name in (self._mcp_tools or {})
            and tool_name not in (self._local_tools or {})
        )
    
    def is_terminal_tool(self, tool_name: str) -> bool:
        """Check if tool should skip synthesis pass."""
        # Local terminal tools
        if self._local_tools and tool_name in self._local_tools:
            return self._local_tools[tool_name].is_terminal
        # MCP tools are typically terminal (return rich results)
        if self._mcp_tools and tool_name in self._mcp_tools:
            return True
        return False
    
    async def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: int | None = None,
    ) -> dict[str, Any]:
        """Execute a tool call via local or MCP.
        
        Returns:
            {"ok": True, "data": {...}, "markdown": "..."}
            {"ok": False, "error": "...", "markdown": "..."}
        """
        # Ensure initialized
        if not self._initialized:
            await self.initialize()
        
        # Normalize tool name (aliases)
        if tool_name == "imagine":
            tool_name = "image_generate"
        elif tool_name == "request":
            tool_name = "http_request"
        
        # Priority 1: Local tool
        if self.is_local_tool(tool_name):
            logger.info(f"[dispatch] Executing LOCAL: {tool_name}")
            return self._execute_local(tool_name, arguments, session_id)
        
        # Priority 2: MCP tool
        if self.is_mcp_tool(tool_name):
            logger.info(f"[dispatch] Executing MCP: {tool_name}")
            return await self._execute_mcp(tool_name, arguments)
        
        # Unknown tool
        available = list((self._local_tools or {}).keys()) + list((self._mcp_tools or {}).keys())
        return {
            "ok": False,
            "error": f"Unknown tool: {tool_name}",
            "markdown": f"**Error:** Unknown tool `{tool_name}`.\n\nAvailable tools: {', '.join(sorted(set(available)))}",
        }
    
    def _execute_local(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: int | None,
    ) -> dict[str, Any]:
        """Execute a local tool synchronously."""
        try:
            from app.tools.registry import execute_tool
            return execute_tool(tool_name, arguments, session_id=session_id)
        except Exception as e:
            logger.error(f"[dispatch] Local tool error: {tool_name} - {e}")
            return {
                "ok": False,
                "error": str(e),
                "markdown": f"**Error executing {tool_name}:** {e}",
            }
    
    async def _execute_mcp(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an MCP tool via HTTP."""
        try:
            from app.mcp import get_mcp_client
            client = get_mcp_client()
            
            if not client or not client.token:
                return {
                    "ok": False,
                    "error": "MCP server unavailable",
                    "markdown": f"**Error:** MCP server is not available. Cannot execute `{tool_name}`.",
                }
            
            result = await client.execute(tool_name, arguments)
            return result
        
        except Exception as e:
            logger.error(f"[dispatch] MCP tool error: {tool_name} - {e}")
            return {
                "ok": False,
                "error": str(e),
                "markdown": f"**Error executing MCP tool {tool_name}:** {e}",
            }


# Singleton instance
_dispatcher: HybridDispatcher | None = None


def get_dispatcher() -> HybridDispatcher:
    """Get or create the singleton dispatcher."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = HybridDispatcher()
    return _dispatcher


async def dispatch_tool(
    tool_name: str,
    arguments: dict[str, Any],
    session_id: int | None = None,
) -> dict[str, Any]:
    """Convenience function to dispatch a tool call."""
    dispatcher = get_dispatcher()
    return await dispatcher.dispatch(tool_name, arguments, session_id)


async def discover_all_tools() -> list[ToolInfo]:
    """Discover all available tools (local + MCP)."""
    dispatcher = get_dispatcher()
    await dispatcher.initialize()
    return dispatcher.get_all_tools()
