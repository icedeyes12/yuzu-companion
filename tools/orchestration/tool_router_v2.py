# Tool Router Module V2
# Routes to internal tools, MCP stdio, or MCP HTTP per roadmap spec

import subprocess
import json
import requests
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from database import Database
from .intent_detector_v2 import ToolIntent
from ..registry import execute_tool as execute_internal_tool


@dataclass
class ToolResult:
    """
    Result of tool execution per roadmap spec.
    
    Roadmap: Phase 2.2.B - ToolRouter output
    """
    tool_type: str  # 'internal' | 'mcp_stdio' | 'mcp_http'
    tool_name: str
    status: str  # 'success' | 'error' | 'timeout'
    result: Any = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    execution_id: Optional[int] = None
    display_data: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class MCPServer:
    """MCP server configuration per roadmap Phase 1.1."""
    id: int
    name: str
    transport: str  # 'stdio' | 'http'
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    url: Optional[str] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    is_active: bool = True
    is_connected: bool = False


class ToolRouter:
    """
    Routes tool execution to appropriate handler.
    
    Roadmap: Phase 2.2.B - "Internal tools, MCP stdio, MCP HTTP"
    """
    
    # Timeouts per tool type (seconds)
    TIMEOUTS = {
        'image_generate': 120,
        'web_search': 30,
        'weather': 30,
        'memory_search': 10,
        'memory_sql': 10,
        'http_request': 60,
        'mcp_stdio': 30,
        'mcp_http': 60,
    }
    
    def __init__(self):
        self._mcp_servers: Dict[str, MCPServer] = {}
        self._mcp_processes: Dict[str, subprocess.Popen] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._load_mcp_servers()
    
    def execute(self, tool_intent: ToolIntent, session_id: Optional[int] = None) -> ToolResult:
        """
        Execute tool based on intent.
        
        Args:
            tool_intent: Detected intent with tool name and params
            session_id: Current chat session for context
            
        Returns:
            ToolResult with execution outcome
        """
        start_time = datetime.now()
        
        # Route based on tool type per roadmap
        if tool_intent.tool_type == 'internal':
            result = self._execute_internal(tool_intent, session_id)
        elif tool_intent.tool_type == 'mcp_stdio':
            result = self._execute_mcp_stdio(tool_intent, session_id)
        elif tool_intent.tool_type == 'mcp_http':
            result = self._execute_mcp_http(tool_intent, session_id)
        else:
            result = ToolResult(
                tool_type='unknown',
                tool_name=tool_intent.tool_name,
                status='error',
                error_message=f"Unknown tool type: {tool_intent.tool_type}"
            )
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        result.execution_time_ms = execution_time
        
        # Save to database for audit trail (per roadmap)
        result.execution_id = self._save_execution(tool_intent, result, session_id)
        
        return result
    
    def _execute_internal(self, tool_intent: ToolIntent, session_id: Optional[int]) -> ToolResult:
        """Execute internal yuzu tool."""
        tool_name = tool_intent.tool_name
        params = tool_intent.params
        
        try:
            timeout = self.TIMEOUTS.get(tool_name, 30)
            
            # Execute via existing registry
            future = self._executor.submit(
                execute_internal_tool,
                tool_name,
                params,
                session_id
            )
            
            try:
                raw_result = future.result(timeout=timeout)
                
                return ToolResult(
                    tool_type='internal',
                    tool_name=tool_name,
                    status='success',
                    result=raw_result
                )
                
            except FutureTimeoutError:
                return ToolResult(
                    tool_type='internal',
                    tool_name=tool_name,
                    status='timeout',
                    error_message=f"Tool execution timed out after {timeout}s"
                )
                
        except Exception as e:
            return ToolResult(
                tool_type='internal',
                tool_name=tool_name,
                status='error',
                error_message=str(e)
            )
    
    def _execute_mcp_stdio(self, tool_intent: ToolIntent, session_id: Optional[int]) -> ToolResult:
        """Execute MCP tool via stdio transport."""
        server_name = tool_intent.params.get('server', 'default')
        tool_name = tool_intent.tool_name
        tool_params = tool_intent.params.get('args', {})
        
        server = self._mcp_servers.get(server_name)
        if not server:
            return ToolResult(
                tool_type='mcp_stdio',
                tool_name=tool_name,
                status='error',
                error_message=f"MCP server '{server_name}' not found"
            )
        
        try:
            # Spawn MCP process if not running
            if server_name not in self._mcp_processes:
                process = subprocess.Popen(
                    [server.command] + server.args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env={**os.environ, **server.env_vars}
                )
                self._mcp_processes[server_name] = process
                server.is_connected = True
            
            process = self._mcp_processes[server_name]
            
            # Send JSON-RPC request per MCP spec
            request = {
                "jsonrpc": "2.0",
                "method": f"tools/{tool_name}",
                "params": tool_params,
                "id": 1
            }
            
            process.stdin.write(json.dumps(request) + '\n')
            process.stdin.flush()
            
            # Read response with timeout
            timeout = self.TIMEOUTS.get('mcp_stdio', 30)
            
            future = self._executor.submit(process.stdout.readline)
            try:
                response_line = future.result(timeout=timeout)
                response = json.loads(response_line)
                
                if 'error' in response:
                    return ToolResult(
                        tool_type='mcp_stdio',
                        tool_name=tool_name,
                        status='error',
                        error_message=response['error'].get('message', 'MCP error')
                    )
                
                return ToolResult(
                    tool_type='mcp_stdio',
                    tool_name=tool_name,
                    status='success',
                    result=response.get('result')
                )
                
            except FutureTimeoutError:
                return ToolResult(
                    tool_type='mcp_stdio',
                    tool_name=tool_name,
                    status='timeout',
                    error_message=f"MCP stdio call timed out after {timeout}s"
                )
                
        except Exception as e:
            return ToolResult(
                tool_type='mcp_stdio',
                tool_name=tool_name,
                status='error',
                error_message=str(e)
            )
    
    def _execute_mcp_http(self, tool_intent: ToolIntent, session_id: Optional[int]) -> ToolResult:
        """Execute MCP tool via HTTP transport."""
        server_name = tool_intent.params.get('server', 'default')
        tool_name = tool_intent.tool_name
        tool_params = tool_intent.params.get('args', {})
        
        server = self._mcp_servers.get(server_name)
        if not server or not server.url:
            return ToolResult(
                tool_type='mcp_http',
                tool_name=tool_name,
                status='error',
                error_message=f"MCP HTTP server '{server_name}' not found or no URL"
            )
        
        try:
            # Send HTTP POST per MCP HTTP spec
            url = f"{server.url}/tools/{tool_name}"
            timeout = self.TIMEOUTS.get('mcp_http', 60)
            
            response = requests.post(
                url,
                json=tool_params,
                timeout=timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                return ToolResult(
                    tool_type='mcp_http',
                    tool_name=tool_name,
                    status='success',
                    result=response.json()
                )
            else:
                return ToolResult(
                    tool_type='mcp_http',
                    tool_name=tool_name,
                    status='error',
                    error_message=f"HTTP {response.status_code}: {response.text[:200]}"
                )
                
        except requests.Timeout:
            return ToolResult(
                tool_type='mcp_http',
                tool_name=tool_name,
                status='timeout',
                error_message=f"MCP HTTP call timed out"
            )
        except Exception as e:
            return ToolResult(
                tool_type='mcp_http',
                tool_name=tool_name,
                status='error',
                error_message=str(e)
            )
    
    def _save_execution(self, intent: ToolIntent, result: ToolResult, session_id: Optional[int]) -> Optional[int]:
        """Save execution to database for audit trail."""
        try:
            from database import Database
            execution_id = Database.save_tool_execution(
                session_id=session_id,
                tool_type=intent.tool_type,
                tool_name=intent.tool_name,
                input_params=intent.params,
                status=result.status,
                output_result=result.result if result.status == 'success' else None,
                error_message=result.error_message
            )
            return execution_id
        except Exception as e:
            print(f"[ToolRouter] Failed to save execution: {e}")
            return None
    
    def _load_mcp_servers(self):
        """Load MCP server configurations from database."""
        try:
            servers = Database.get_mcp_servers(active_only=True)
            for server in servers:
                self._mcp_servers[server['name']] = MCPServer(**server)
            print(f"[ToolRouter] Loaded {len(self._mcp_servers)} MCP servers")
        except Exception as e:
            print(f"[ToolRouter] No MCP servers configured: {e}")
    
    def add_mcp_server(self, server: MCPServer) -> bool:
        """Add and persist new MCP server."""
        try:
            # Save to database
            server_id = Database.add_mcp_server(
                name=server.name,
                transport=server.transport,
                command=server.command,
                args=server.args,
                url=server.url,
                env_vars=server.env_vars
            )
            
            if server_id:
                server.id = server_id
                self._mcp_servers[server.name] = server
                return True
            return False
            
        except Exception as e:
            print(f"[ToolRouter] Failed to add MCP server: {e}")
            return False
    
    def disconnect_all_mcp(self):
        """Clean up all MCP connections."""
        for name, process in self._mcp_processes.items():
            try:
                process.terminate()
                process.wait(timeout=2)
            except:
                process.kill()
        self._mcp_processes.clear()
        print("[ToolRouter] All MCP connections closed")