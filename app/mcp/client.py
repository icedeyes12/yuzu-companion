# FILE: app/mcp/client.py
# DESCRIPTION: HTTP client for Zo MCP sandbox tools
#              Bridges local Yuzu instance to Zo's remote tool ecosystem
#
# Architecture:
#   - Single httpx AsyncClient per instance (connection pooling)
#   - Bearer token auth from ZO_ACCESS_TOKEN env var (NOT hardcoded)
#   - JSON-RPC 2.0 protocol (Zo MCP endpoint)
#   - Tool discovery via tools/list method
#   - Execute tools via tools/call method
#
# Termux Compatibility:
#   - Pure Python + httpx (no Rust dependencies)
#   - Async-first but provides sync wrappers for legacy code

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger(__name__)

# Zo MCP endpoint (JSON-RPC 2.0)
MCP_ENDPOINT = "https://api.zo.computer/mcp"
DEFAULT_TIMEOUT = 60.0

# Global singleton (lazy-initialized)
_mcp_client: MCPClient | None = None


@dataclass
class MCPTool:
    """Represents a discovered MCP tool definition."""
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    
    def to_llm_schema(self) -> dict:
        """Convert to OpenAI function-calling schema format."""
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


class MCPClient:
    """Async HTTP client for Zo MCP tools.
    
    Usage:
        client = get_mcp_client()  # singleton
        tools = await client.discover_tools()
        result = await client.call_tool("web_search", {"query": "hello", "time_range": "anytime"})
    
    For sync contexts:
        result = client.call_tool_sync("web_search", {"query": "hello"})
    """
    
    def __init__(
        self,
        token: str | None = None,
        base_url: str = MCP_ENDPOINT,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.token = token or os.environ.get("ZO_ACCESS_TOKEN", "")
        self.base_url = base_url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._tools_cache: list[MCPTool] | None = None
        self._rpc_id: int = 0
    
    def _next_id(self) -> int:
        """Generate unique RPC request ID."""
        self._rpc_id = (self._rpc_id + 1) % 100000
        return self._rpc_id
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init the async HTTP client."""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client
    
    async def _rpc_request(self, method: str, params: dict[str, Any] | None = None) -> dict:
        """Send a JSON-RPC 2.0 request."""
        client = await self._get_client()
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        resp = await client.post("/", json=payload)
        
        if resp.status_code != 200:
            raise Exception(f"MCP HTTP {resp.status_code}: {resp.text[:200]}")
        
        result = resp.json()
        
        # Handle JSON-RPC error response
        if "error" in result:
            error = result["error"]
            raise Exception(f"MCP error {error.get('code')}: {error.get('message')}")
        
        return result
    
    async def discover_tools(self, force_refresh: bool = False) -> list[MCPTool]:
        """Discover available tools from Zo MCP server.
        
        Caches results for the lifetime of the client.
        """
        if self._tools_cache is not None and not force_refresh:
            return self._tools_cache
        
        log.info("Discovering Zo MCP tools...")
        
        try:
            result = await self._rpc_request("tools/list")
            tools_data = result.get("result", {}).get("tools", [])
            
            tools = []
            for item in tools_data:
                tools.append(MCPTool(
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    input_schema=item.get("inputSchema", {}),
                ))
            
            self._tools_cache = tools
            log.info(f"Discovered {len(tools)} Zo MCP tools")
            return tools
            
        except Exception as e:
            log.error(f"Zo MCP tool discovery failed: {e}")
            return []
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool on the Zo MCP server.
        
        Returns:
            {"ok": True, "data": ..., "markdown": "..."}
            {"ok": False, "error": "...", "markdown": "..."}
        """
        try:
            log.debug(f"MCP call_tool: {tool_name}({arguments})")
            
            result = await self._rpc_request("tools/call", {
                "name": tool_name,
                "arguments": arguments,
            })
            
            # Extract result from JSON-RPC response
            tool_result = result.get("result", {})
            
            # Different MCP servers return different shapes
            # Try common patterns
            content = tool_result.get("content", [])
            if isinstance(content, list) and len(content) > 0:
                # Anthropic MCP style: content[] with text
                text = content[0].get("text", str(tool_result))
            else:
                text = str(tool_result)
            
            return {
                "ok": True,
                "data": tool_result,
                "markdown": text,
            }
            
        except Exception as e:
            log.error(f"MCP call_tool error: {tool_name} - {e}")
            return {
                "ok": False,
                "error": str(e),
                "markdown": f"<details><summary>MCP Error: {tool_name}</summary>\n\n{str(e)}\n</details>",
            }
    
    def call_tool_sync(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Synchronous wrapper for legacy code paths."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop is not None:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.call_tool(tool_name, arguments),
                )
                return future.result()
        else:
            return asyncio.run(self.call_tool(tool_name, arguments))
    
    async def close(self) -> None:
        """Clean up the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def get_mcp_client() -> MCPClient:
    """Get or create the singleton MCP client."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


async def discover_mcp_tools() -> list[MCPTool]:
    """Convenience function to discover tools from singleton client."""
    client = get_mcp_client()
    return await client.discover_tools()
