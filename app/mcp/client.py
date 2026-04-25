# FILE: app/mcp/client.py
# DESCRIPTION: HTTP client for Zo MCP sandbox tools
#              Bridges local Yuzu instance to Zo's remote tool ecosystem
#
# Architecture:
#   - Single httpx AsyncClient per instance (connection pooling)
#   - Bearer token auth from ZO_MCP_TOKEN env var
#   - Tool discovery at startup (caches available tools)
#   - Execute tools via POST /mcp with tool_name + arguments
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

MCP_ENDPOINT = "https://api.zo.computer/mcp"
MCP_DISCOVERY_ENDPOINT = "https://api.zo.computer/mcp/tools"
DEFAULT_TIMEOUT = 60.0


@dataclass
class MCPTool:
    """Represents a discovered MCP tool definition."""
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    
    def to_llm_schema(self) -> dict:
        """Convert to OpenAI function-calling schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class MCPClient:
    """Async HTTP client for Zo MCP tools.
    
    Usage:
        client = MCPClient()
        tools = await client.discover_tools()
        result = await client.execute("zo_search", {"query": "hello"})
    
    For sync contexts:
        result = client.execute_sync("zo_search", {"query": "hello"})
    """
    
    def __init__(
        self,
        token: str | None = None,
        base_url: str = MCP_ENDPOINT,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.token = token or os.environ.get("ZO_MCP_TOKEN", "")
        self.base_url = base_url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._tools_cache: list[MCPTool] | None = None
        self._is_available: bool | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init the async HTTP client."""
        if self._client is None:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client
    
    async def is_available(self) -> bool:
        """Check if MCP server is reachable."""
        if self._is_available is not None:
            return self._is_available
        
        try:
            client = await self._get_client()
            resp = await client.get("/health", timeout=5.0)
            self._is_available = resp.status_code == 200
        except Exception as e:
            log.debug(f"MCP health check failed: {e}")
            self._is_available = False
        
        return self._is_available
    
    async def discover_tools(self, force_refresh: bool = False) -> list[MCPTool]:
        """Fetch available tools from MCP server.
        
        Caches results for the lifetime of the client.
        """
        if self._tools_cache is not None and not force_refresh:
            return self._tools_cache
        
        try:
            client = await self._get_client()
            resp = await client.get("/tools")
            
            if resp.status_code != 200:
                log.warning(f"MCP tool discovery failed: HTTP {resp.status_code}")
                return []
            
            data = resp.json()
            tools = []
            
            for item in data.get("tools", []):
                tools.append(MCPTool(
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    parameters=item.get("parameters", {}),
                ))
            
            self._tools_cache = tools
            log.info(f"Discovered {len(tools)} MCP tools")
            return tools
            
        except Exception as e:
            log.warning(f"MCP tool discovery error: {e}")
            return []
    
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool on the MCP server.
        
        Returns:
            {"ok": True, "data": ..., "markdown": ...}
            {"ok": False, "error": ..., "markdown": ...}
        """
        try:
            client = await self._get_client()
            
            payload = {
                "tool_name": tool_name,
                "arguments": arguments,
            }
            
            log.debug(f"MCP execute: {tool_name}({arguments})")
            
            resp = await client.post("/", json=payload)
            
            if resp.status_code == 200:
                result = resp.json()
                log.debug(f"MCP result: {tool_name} -> ok={result.get('ok')}")
                return result
            else:
                error_text = resp.text[:200]
                log.warning(f"MCP execute failed: HTTP {resp.status_code} - {error_text}")
                return {
                    "ok": False,
                    "error": f"MCP server error: HTTP {resp.status_code}",
                    "markdown": f"<details><summary>MCP Error</summary>\n\n{error_text}\n</details>",
                }
                
        except httpx.TimeoutException:
            log.warning(f"MCP timeout: {tool_name}")
            return {
                "ok": False,
                "error": "MCP request timed out",
                "markdown": "<details><summary>MCP Timeout</summary>\n\nRequest timed out.\n</details>",
            }
        except Exception as e:
            log.error(f"MCP execute error: {e}")
            return {
                "ok": False,
                "error": str(e),
                "markdown": f"<details><summary>MCP Error</summary>\n\n{e}\n</details>",
            }
    
    def execute_sync(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Synchronous wrapper for legacy code paths.
        
        Uses asyncio.run() internally. NOT suitable for hot loops.
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop is not None:
            # Already in async context — create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.execute(tool_name, arguments),
                )
                return future.result()
        else:
            return asyncio.run(self.execute(tool_name, arguments))
    
    async def close(self) -> None:
        """Clean up the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# Singleton instance
_mcp_client: MCPClient | None = None


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
