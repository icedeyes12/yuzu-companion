"""
ToolRouter - Routes tool execution to the correct implementation

Handles execution for:
- Internal tools (Python functions)
- MCP stdio tools (subprocess-based)
- MCP HTTP tools (HTTP-based)
"""

import json
import asyncio
import subprocess
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from database import Database
from tools.registry import execute_tool as execute_internal_tool


class ToolType(Enum):
    """Types of tools supported"""
    INTERNAL = "internal"
    MCP_STDIO = "mcp_stdio"
    MCP_HTTP = "mcp_http"


@dataclass
class ToolResult:
    """Result of tool execution"""
    success: bool
    tool_name: str
    tool_type: ToolType
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "tool_type": self.tool_type.value,
            "output": self.output,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata
        }


class ToolRouter:
    """
    Routes tool execution to the appropriate handler.
    
    Supports:
    - Internal tools (Python modules)
    - MCP stdio tools (spawned subprocesses)
    - MCP HTTP tools (HTTP requests)
    """
    
    def __init__(self):
        self._mcp_processes: Dict[str, subprocess.Popen] = {}
    
    def execute(self, tool_name: str, params: Dict[str, Any], 
                tool_type: ToolType = ToolType.INTERNAL,
                session_id: int = None,
                mcp_server_name: str = None) -> ToolResult:
        """
        Execute a tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            params: Parameters for the tool
            tool_type: Type of tool (internal/mcp_stdio/mcp_http)
            session_id: Current session ID for context
            mcp_server_name: Name of MCP server (for MCP tools)
        
        Returns:
            ToolResult with execution outcome
        """
        import time
        start_time = time.time()
        
        try:
            if tool_type == ToolType.INTERNAL:
                result = self._execute_internal(tool_name, params, session_id)
            elif tool_type == ToolType.MCP_STDIO:
                result = self._execute_mcp_stdio(tool_name, params, mcp_server_name)
            elif tool_type == ToolType.MCP_HTTP:
                result = self._execute_mcp_http(tool_name, params, mcp_server_name)
            else:
                result = ToolResult(
                    success=False,
                    tool_name=tool_name,
                    tool_type=tool_type,
                    output=None,
                    error=f"Unknown tool type: {tool_type}"
                )
            
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result
            
        except Exception as e:
            import traceback
            error_msg = f"Tool execution failed: {str(e)}"
            print(f"[ToolRouter] {error_msg}")
            print(traceback.format_exc())
            
            return ToolResult(
                success=False,
                tool_name=tool_name,
                tool_type=tool_type,
                output=None,
                error=error_msg,
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _execute_internal(self, tool_name: str, params: Dict[str, Any], 
                         session_id: int = None) -> ToolResult:
        """Execute internal tool via registry"""
        
        # Check if tool exists in registry
        from tools.registry import _TOOLS
        if tool_name not in _TOOLS:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                tool_type=ToolType.INTERNAL,
                output=None,
                error=f"Unknown internal tool: {tool_name}"
            )
        
        # Execute via registry
        output = execute_internal_tool(tool_name, params, session_id=session_id)
        
        return ToolResult(
            success=True,
            tool_name=tool_name,
            tool_type=ToolType.INTERNAL,
            output=output,
            metadata={"raw_output": True}  # Indicates output needs processing
        )
    
    def _execute_mcp_stdio(self, tool_name: str, params: Dict[str, Any],
                          server_name: str = None) -> ToolResult:
        """
        Execute MCP tool via stdio transport.
        
        MCP stdio uses JSON-RPC 2.0 protocol over subprocess stdin/stdout.
        """
        if not server_name:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                tool_type=ToolType.MCP_STDIO,
                output=None,
                error="MCP server name required for stdio execution"
            )
        
        # Get MCP server config
        server_config = Database.get_mcp_server(name=server_name)
        if not server_config:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                tool_type=ToolType.MCP_STDIO,
                output=None,
                error=f"MCP server not found: {server_name}"
            )
        
        try:
            # Build MCP JSON-RPC request
            request_id = f"tool_{tool_name}_{os.urandom(4).hex()}"
            mcp_request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": params
                }
            }
            
            # Check if we have a running process for this server
            if server_name not in self._mcp_processes:
                # Start MCP server process
                command = server_config["command"]
                args = server_config.get("args", [])
                env_vars = server_config.get("env_vars", {})
                
                # Build command
                cmd = [command] + args
                
                # Prepare environment
                env = os.environ.copy()
                env.update(env_vars)
                
                # Start process
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True
                )
                
                self._mcp_processes[server_name] = process
            
            process = self._mcp_processes[server_name]
            
            # Send request
            request_json = json.dumps(mcp_request) + "\n"
            process.stdin.write(request_json)
            process.stdin.flush()
            
            # Read response
            response_line = process.stdout.readline()
            if not response_line:
                stderr = process.stderr.read() if process.stderr else ""
                return ToolResult(
                    success=False,
                    tool_name=tool_name,
                    tool_type=ToolType.MCP_STDIO,
                    output=None,
                    error=f"MCP server process ended. stderr: {stderr}"
                )
            
            response = json.loads(response_line)
            
            if "error" in response:
                return ToolResult(
                    success=False,
                    tool_name=tool_name,
                    tool_type=ToolType.MCP_STDIO,
                    output=None,
                    error=response["error"].get("message", "MCP error")
                )
            
            return ToolResult(
                success=True,
                tool_name=tool_name,
                tool_type=ToolType.MCP_STDIO,
                output=response.get("result", {}),
                metadata={"server": server_name}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                tool_type=ToolType.MCP_STDIO,
                output=None,
                error=f"MCP stdio execution failed: {str(e)}"
            )
    
    def _execute_mcp_http(self, tool_name: str, params: Dict[str, Any],
                         server_name: str = None) -> ToolResult:
        """
        Execute MCP tool via HTTP transport.
        
        MCP HTTP uses JSON-RPC 2.0 protocol over HTTP.
        """
        if not server_name:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                tool_type=ToolType.MCP_HTTP,
                output=None,
                error="MCP server name required for HTTP execution"
            )
        
        # Get MCP server config
        server_config = Database.get_mcp_server(name=server_name)
        if not server_config:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                tool_type=ToolType.MCP_HTTP,
                output=None,
                error=f"MCP server not found: {server_name}"
            )
        
        server_url = server_config.get("url")
        if not server_url:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                tool_type=ToolType.MCP_HTTP,
                output=None,
                error=f"MCP server {server_name} has no URL configured"
            )
        
        try:
            import requests
            
            # Build MCP JSON-RPC request
            request_id = f"tool_{tool_name}_{os.urandom(4).hex()}"
            mcp_request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": params
                }
            }
            
            # Send HTTP request
            response = requests.post(
                server_url,
                json=mcp_request,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                return ToolResult(
                    success=False,
                    tool_name=tool_name,
                    tool_type=ToolType.MCP_HTTP,
                    output=None,
                    error=f"MCP HTTP error: {response.status_code}"
                )
            
            data = response.json()
            
            if "error" in data:
                return ToolResult(
                    success=False,
                    tool_name=tool_name,
                    tool_type=ToolType.MCP_HTTP,
                    output=None,
                    error=data["error"].get("message", "MCP error")
                )
            
            return ToolResult(
                success=True,
                tool_name=tool_name,
                tool_type=ToolType.MCP_HTTP,
                output=data.get("result", {}),
                metadata={"server": server_name, "url": server_url}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                tool_type=ToolType.MCP_HTTP,
                output=None,
                error=f"MCP HTTP execution failed: {str(e)}"
            )
    
    def get_tool_type(self, tool_name: str) -> ToolType:
        """
        Determine the tool type for a given tool name.
        
        Checks:
        1. Internal tools registry
        2. MCP servers for registered tools
        """
        # Check internal tools
        from tools.registry import _TOOLS
        if tool_name in _TOOLS:
            return ToolType.INTERNAL
        
        # Check MCP servers
        mcp_servers = Database.list_mcp_servers(active_only=True)
        for server in mcp_servers:
            # In a full implementation, we'd query the MCP server
            # for its available tools. For now, assume any unknown
            # tool might be MCP.
            pass
        
        # Default to internal
        return ToolType.INTERNAL
    
    def shutdown(self):
        """Shutdown all MCP server processes"""
        for name, process in self._mcp_processes.items():
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception as e:
                print(f"[ToolRouter] Failed to terminate {name}: {e}")
        
        self._mcp_processes.clear()


# Singleton instance
_tool_router = None

def get_tool_router() -> ToolRouter:
    """Get or create ToolRouter singleton"""
    global _tool_router
    if _tool_router is None:
        _tool_router = ToolRouter()
    return _tool_router
