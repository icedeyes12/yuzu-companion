# FILE: app/dispatch/hybrid.py
# DESCRIPTION: Hybrid tool dispatcher — routes to local or Zo MCP execution
#
# Architecture:
#   - Local tools: app/tools/registry.py (image_generate, request, memory_*)
#   - Zo MCP tools: app/mcp/client.py (56 remote tools via JSON-RPC)
#
# Priority Dispatch:
#   1. Local tool? → app/tools/registry.execute_tool()
#   2. MCP tool? → app/mcp/client.call_tool()
#   3. Unknown? → error
#
# Wire to agentic loop:
#   from app.dispatch.hybrid import get_dispatcher, dispatch_tool, discover_all_tools
#
# Environment:
#   ZO_ACCESS_TOKEN must be set (from .env)

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.mcp.client import MCPClient, get_mcp_client

log = logging.getLogger(__name__)

# MCP tool prefix for routing
MCP_TOOL_PREFIX = "zo_"


@dataclass
class HybridTool:
    """Unified tool definition for hybrid dispatch."""
    name: str
    description: str
    is_local: bool
    is_mcp: bool = False
    input_schema: dict[str, Any] = field(default_factory=dict)
    source: str = "local"  # "local" or "mcp"
    
    @property
    def parameters(self) -> dict[str, Any]:
        """Alias for input_schema for API compatibility."""
        return self.input_schema
    
    def __post_init__(self):
        # Auto-set source based on is_local/is_mcp
        if self.is_mcp:
            self.source = "mcp"
        else:
            self.source = "local"
    
    def to_llm_schema(self) -> dict:
        """Convert to OpenAI function-calling schema."""
        schema = self.input_schema.get("properties", {})
        required = self.input_schema.get("required", [])
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": schema,
                    "required": required,
                },
            },
        }


class HybridDispatcher:
    """Hybrid dispatcher that routes to local OR Zo MCP tools.
    
    Usage:
        dispatcher = get_dispatcher()
        await dispatcher.initialize()
        result = await dispatcher.execute("web_search", {"query": "hello", "time_range": "anytime"})
    """
    
    def __init__(self, mcp_token: str | None = None):
        self._local_tools: dict[str, Any] = {}
        self._mcp_tools: dict[str, HybridTool] = {}
        self._initialized: bool = False
        self._mcp_client: MCPClient | None = None
    
    async def initialize(self) -> None:
        """Discover all available tools (local + Zo MCP)."""
        if self._initialized:
            return
        
        log.info("Initializing hybrid dispatcher...")
        
        # Load local tools from registry (including aliases)
        from app.tools.registry import (
            execute_tool as exec_local,
            _TOOL_DEFINITIONS,
            _collect_definitions,
        )
        _collect_definitions()
        
        # Register all tools including aliases
        for name, tool_def in _TOOL_DEFINITIONS.items():
            self._local_tools[name] = {
                "def": tool_def,
                "execute": exec_local,
            }
        log.info(f"Loaded {len(self._local_tools)} local tools (with aliases)")
        
        # Discover Zo MCP tools
        self._mcp_client = get_mcp_client()
        if self._mcp_client.token:
            mcp_tools = await self._mcp_client.discover_tools()
            for tool in mcp_tools:
                hybrid_tool = HybridTool(
                    name=tool.name,
                    description=tool.description,
                    is_local=False,
                    is_mcp=True,
                    input_schema=tool.input_schema,
                )
                self._mcp_tools[tool.name] = hybrid_tool
            log.info(f"Discovered {len(self._mcp_tools)} Zo MCP tools")
        else:
            log.warning("ZO_ACCESS_TOKEN not set - MCP tools unavailable")
        
        self._initialized = True
    
    def is_local_tool(self, tool_name: str) -> bool:
        """Check if tool is a local tool."""
        if self._local_tools:
            return tool_name in self._local_tools
        # Lazy fallback for common local tools before init
        return tool_name in (
            "imagine", "image_generate", "request", "http_request",
            "memory_store", "memory_search", "file_read", "list_dir"
        )
    
    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if tool is a Zo MCP tool.
        
        Handles both prefixed (zo_search) and non-prefixed (web_search) names.
        """
        # Strip zo_ prefix if present
        base_name = tool_name[3:] if tool_name.startswith("zo_") else tool_name
        return base_name in self._mcp_tools or tool_name in self._mcp_tools
    
    # Terminal tools that should end the agentic loop when successful
    TERMINAL_TOOLS = frozenset([
        "complete",
        "finish",
        "submit",
        "final_answer",
    ])
    
    def is_terminal_tool(self, tool_name: str) -> bool:
        """Check if tool should terminate the agentic loop."""
        base_name = tool_name[3:] if tool_name.startswith("zo_") else tool_name
        return base_name in self.TERMINAL_TOOLS
    
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: int | None = None,
    ) -> dict[str, Any]:
        """Execute a tool (local or MCP).
        
        Returns:
            {"ok": True, "data": ..., "markdown": "..."}
            {"ok": False, "error": "...", "markdown": "..."}
        """
        log.info(f"HybridDispatcher.execute: {tool_name} | local={self.is_local_tool(tool_name)} | mcp={self.is_mcp_tool(tool_name)}")
        
        if self.is_local_tool(tool_name):
            log.info(f"Executing local tool: {tool_name}")
            return await self._execute_local(tool_name, arguments, session_id)
        elif self.is_mcp_tool(tool_name):
            log.info(f"Executing MCP tool: {tool_name}")
            return await self._execute_mcp(tool_name, arguments)
        else:
            log.warning(f"Unknown tool: {tool_name}")
            return {
                "ok": False,
                "error": f"Unknown tool: {tool_name}",
                "markdown": f"<details><summary>Unknown Tool</summary>\n\nTool '{tool_name}' not found.\n</details>",
            }
    
    async def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: int | None = None,
    ) -> dict[str, Any]:
        """Alias for execute() - called by orchestrator.
        
        Also handles zo_ prefix normalization for MCP tools.
        """
        # Normalize tool name: strip zo_ prefix for MCP tools
        base_name = tool_name[3:] if tool_name.startswith("zo_") else tool_name
        
        # Use base name for MCP tools, original for local
        if base_name in self._mcp_tools:
            return await self._execute_mcp(base_name, arguments)
        elif tool_name in self._local_tools:
            return await self._execute_local(tool_name, arguments, session_id)
        else:
            return await self.execute(tool_name, arguments, session_id)
    
    async def _execute_local(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: int | None = None,
    ) -> dict[str, Any]:
        """Execute a local tool."""
        try:
            from app.tools.registry import execute_tool
            return execute_tool(tool_name, arguments, session_id=session_id)
        except Exception as e:
            log.error(f"Local tool error: {tool_name} - {e}")
            return {
                "ok": False,
                "error": str(e),
                "markdown": f"<details><summary>Local Tool Error</summary>\n\n{str(e)}\n</details>",
            }
    
    async def _execute_mcp(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a Zo MCP tool.
        
        Normalizes zo_ prefix if present.
        """
        if not self._mcp_client:
            return {
                "ok": False,
                "error": "MCP client not initialized",
                "markdown": "<details><summary>MCP Error</summary>\n\nMCP client not available.\n</details>",
            }
        
        # Normalize tool name: strip zo_ prefix for actual MCP call
        base_name = tool_name[3:] if tool_name.startswith("zo_") else tool_name
        
        try:
            result = await self._mcp_client.call_tool(base_name, arguments)
            return result
        except Exception as e:
            log.error(f"MCP tool error: {tool_name} - {e}")
            return {
                "ok": False,
                "error": str(e),
                "markdown": f"<details><summary>MCP Error: {tool_name}</summary>\n\n{str(e)}\n</details>",
            }
    
    def get_all_tools(self) -> list[HybridTool]:
        """Get all available tools (local + MCP)."""
        local_tools = [
            HybridTool(
                name=name,
                description=info["def"].description,
                is_local=True,
                is_mcp=False,
            )
            for name, info in self._local_tools.items()
        ]
        return local_tools + list(self._mcp_tools.values())
    
    def get_mcp_tools(self) -> list[HybridTool]:
        """Get only Zo MCP tools."""
        return list(self._mcp_tools.values())
    
    def get_local_tools(self) -> list[HybridTool]:
        """Get only local tools."""
        return [
            HybridTool(
                name=name,
                description=info["def"].description,
                is_local=True,
                is_mcp=False,
            )
            for name, info in self._local_tools.items()
        ]
    
    def _get_mcp_tools_sync(self) -> list[HybridTool]:
        """Sync wrapper for MCP tool discovery (for status checks)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop is not None:
            # Already in async context - run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._mcp_client.discover_tools() if self._mcp_client else []
                )
                tools = future.result()
        else:
            # Not in async context
            if self._mcp_client:
                tools = asyncio.run(self._mcp_client.discover_tools())
            else:
                tools = []
        
        # Convert to HybridTool
        return [
            HybridTool(
                name=tool.name,
                description=tool.description,
                is_local=False,
                is_mcp=True,
                input_schema=tool.input_schema,
            )
            for tool in tools
        ]
    
    def get_tools_for_mode(self, profile: dict[str, Any] | None = None) -> list[HybridTool]:
        """Get tools based on agentic mode setting.
        
        Returns:
          - Local tools only if agentic mode is disabled
          - Local + MCP tools if agentic mode is enabled
        """
        from app.agentic_config import is_agentic_mode_enabled
        
        local_tools = self.get_local_tools()
        
        if is_agentic_mode_enabled(profile):
            return local_tools + list(self._mcp_tools.values())
        
        return local_tools


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
    if not dispatcher._initialized:
        await dispatcher.initialize()
    return await dispatcher.execute(tool_name, arguments, session_id)


async def discover_all_tools() -> list[HybridTool]:
    """Convenience function to discover all tools."""
    dispatcher = get_dispatcher()
    if not dispatcher._initialized:
        await dispatcher.initialize()
    return dispatcher.get_all_tools()
