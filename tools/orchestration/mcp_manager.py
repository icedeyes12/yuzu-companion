"""
MCP Manager - Handles MCP server lifecycle and tool discovery

Manages:
- MCP server lifecycle (start/stop/restart)
- Connection pooling
- Tool/capability discovery
- Error handling and retry logic
"""

import json
import subprocess
import os
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from database import Database


class ServerStatus(Enum):
    """MCP server status"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    STOPPING = "stopping"


@dataclass
class MCPTool:
    """Represents a tool exposed by an MCP server"""
    name: str
    description: str
    input_schema: Dict = field(default_factory=dict)
    server_name: str = ""


@dataclass
class MCPServerInstance:
    """Runtime instance of an MCP server"""
    name: str
    status: ServerStatus
    process: Optional[subprocess.Popen] = None
    config: Dict = field(default_factory=dict)
    tools: List[MCPTool] = field(default_factory=list)
    last_error: Optional[str] = None
    started_at: Optional[float] = None
    connection_count: int = 0


class MCPManager:
    """
    Manages MCP server lifecycle and interactions.
    
    Supports:
    - stdio transport (subprocess-based)
    - HTTP/SSE transport
    - Auto-restart on failure
    - Tool discovery
    """
    
    def __init__(self):
        self._servers: Dict[str, MCPServerInstance] = {}
        self._lock = threading.Lock()
        self._max_restart_attempts = 3
        self._restart_delay_seconds = 2
    
    def start_server(self, server_name: str) -> bool:
        """
        Start an MCP server by name.
        
        Args:
            server_name: Name of the server to start
        
        Returns:
            True if started successfully
        """
        with self._lock:
            # Get server config from database
            server_config = Database.get_mcp_server(name=server_name)
            if not server_config:
                print(f"[MCPManager] Server not found: {server_name}")
                return False
            
            # Check if already running
            if server_name in self._servers:
                instance = self._servers[server_name]
                if instance.status == ServerStatus.RUNNING:
                    return True
            
            # Create instance
            instance = MCPServerInstance(
                name=server_name,
                status=ServerStatus.STARTING,
                config=server_config
            )
            self._servers[server_name] = instance
            
            # Start based on transport
            transport = server_config.get("transport", "stdio")
            
            try:
                if transport == "stdio":
                    success = self._start_stdio_server(instance)
                elif transport == "http":
                    success = self._start_http_server(instance)
                else:
                    instance.status = ServerStatus.ERROR
                    instance.last_error = f"Unknown transport: {transport}"
                    return False
                
                if success:
                    instance.status = ServerStatus.RUNNING
                    instance.started_at = time.time()
                    
                    # Update database
                    Database.update_mcp_server(
                        server_config["id"],
                        is_connected=True,
                        last_error=None
                    )
                    
                    # Discover tools
                    self._discover_tools(instance)
                    
                    print(f"[MCPManager] Server started: {server_name} ({len(instance.tools)} tools)")
                    return True
                else:
                    instance.status = ServerStatus.ERROR
                    Database.update_mcp_server(
                        server_config["id"],
                        is_connected=False,
                        last_error=instance.last_error
                    )
                    return False
                    
            except Exception as e:
                instance.status = ServerStatus.ERROR
                instance.last_error = str(e)
                print(f"[MCPManager] Failed to start {server_name}: {e}")
                return False
    
    def _start_stdio_server(self, instance: MCPServerInstance) -> bool:
        """Start a stdio transport MCP server"""
        config = instance.config
        command = config.get("command")
        args = config.get("args", [])
        env_vars = config.get("env_vars", {})
        
        if not command:
            instance.last_error = "No command specified"
            return False
        
        try:
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
                text=True,
                bufsize=1
            )
            
            instance.process = process
            instance.status = ServerStatus.RUNNING
            
            # Initialize MCP connection
            return self._initialize_stdio_connection(instance)
            
        except Exception as e:
            instance.last_error = f"Failed to start process: {e}"
            return False
    
    def _start_http_server(self, instance: MCPServerInstance) -> bool:
        """Start an HTTP transport MCP server"""
        config = instance.config
        url = config.get("url")
        
        if not url:
            instance.last_error = "No URL specified"
            return False
        
        # For HTTP, we just verify the endpoint is reachable
        # The actual tool calls will be made via HTTP
        try:
            import requests
            # Send initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": "init",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "yuzu-companion",
                        "version": "1.0.0"
                    }
                }
            }
            
            response = requests.post(
                url,
                json=init_request,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                instance.status = ServerStatus.RUNNING
                return True
            else:
                instance.last_error = f"HTTP {response.status_code}"
                return False
                
        except Exception as e:
            instance.last_error = f"Connection failed: {e}"
            return False
    
    def _initialize_stdio_connection(self, instance: MCPServerInstance) -> bool:
        """Initialize MCP connection via stdio"""
        if not instance.process:
            return False
        
        try:
            # Send initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": "init",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "yuzu-companion",
                        "version": "1.0.0"
                    }
                }
            }
            
            request_json = json.dumps(init_request) + "\n"
            instance.process.stdin.write(request_json)
            instance.process.stdin.flush()
            
            # Read response
            response_line = instance.process.stdout.readline()
            if not response_line:
                instance.last_error = "No response from server"
                return False
            
            response = json.loads(response_line)
            
            if "error" in response:
                instance.last_error = response["error"].get("message", "Init error")
                return False
            
            # Send initialized notification
            notif = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            instance.process.stdin.write(json.dumps(notif) + "\n")
            instance.process.stdin.flush()
            
            # Small delay for server readiness
            import time
            time.sleep(0.2)
            
            return True
            
        except Exception as e:
            instance.last_error = f"Init failed: {e}"
            return False
    
    def _discover_tools(self, instance: MCPServerInstance):
        """Discover tools available on an MCP server"""
        config = instance.config
        transport = config.get("transport", "stdio")
        
        if transport == "stdio":
            self._discover_stdio_tools(instance)
        elif transport == "http":
            self._discover_http_tools(instance)
    
    def _discover_stdio_tools(self, instance: MCPServerInstance):
        """Discover tools via stdio with timeout and error handling"""
        if not instance.process:
            return
        
        try:
            import select
            import time
            
            # Small delay to ensure server is ready
            time.sleep(0.3)
            
            # Send tools/list request
            request = {
                "jsonrpc": "2.0",
                "id": "tools_list",
                "method": "tools/list",
                "params": {}
            }
            
            instance.process.stdin.write(json.dumps(request) + "\n")
            instance.process.stdin.flush()
            
            # Wait for response with timeout
            ready, _, _ = select.select([instance.process.stdout], [], [], 5.0)
            if not ready:
                # Try to get stderr for diagnosis
                stderr_output = ""
                try:
                    import os
                    fd = instance.process.stderr.fileno()
                    ready_err, _, _ = select.select([instance.process.stderr], [], [], 0.5)
                    if ready_err:
                        stderr_output = instance.process.stderr.read(1024)
                except:
                    pass
                
                print(f"[MCPManager] ⚠️ Tool discovery timeout for {instance.name}")
                if stderr_output:
                    print(f"[MCPManager]   stderr: {stderr_output[:200]}")
                return
            
            # Read response
            response_line = instance.process.stdout.readline()
            if not response_line:
                print(f"[MCPManager] ⚠️ No tool response from {instance.name}")
                return
            
            response = json.loads(response_line)
            
            if "error" in response:
                print(f"[MCPManager] ⚠️ Tool discovery error for {instance.name}: {response['error']}")
                return
            
            if "result" in response:
                tools_data = response["result"].get("tools", [])
                instance.tools = [
                    MCPTool(
                        name=t.get("name", ""),
                        description=t.get("description", ""),
                        input_schema=t.get("inputSchema", {}),
                        server_name=instance.name
                    )
                    for t in tools_data
                ]
                print(f"[MCPManager] ✅ {instance.name}: Discovered {len(instance.tools)} tools")
                
        except json.JSONDecodeError as e:
            print(f"[MCPManager] ⚠️ Invalid JSON from {instance.name}: {e}")
        except Exception as e:
            print(f"[MCPManager] ⚠️ Tool discovery failed for {instance.name}: {e}")
    
    def _discover_http_tools(self, instance: MCPServerInstance):
        """Discover tools via HTTP"""
        url = instance.config.get("url")
        if not url:
            return
        
        try:
            import requests
            
            request = {
                "jsonrpc": "2.0",
                "id": "tools_list",
                "method": "tools/list",
                "params": {}
            }
            
            response = requests.post(
                url,
                json=request,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    tools_data = data["result"].get("tools", [])
                    instance.tools = [
                        MCPTool(
                            name=t.get("name", ""),
                            description=t.get("description", ""),
                            input_schema=t.get("inputSchema", {}),
                            server_name=instance.name
                        )
                        for t in tools_data
                    ]
                    
        except Exception as e:
            print(f"[MCPManager] Tool discovery failed for {instance.name}: {e}")
    
    def stop_server(self, server_name: str) -> bool:
        """Stop an MCP server"""
        with self._lock:
            if server_name not in self._servers:
                return True
            
            instance = self._servers[server_name]
            instance.status = ServerStatus.STOPPING
            
            try:
                if instance.process:
                    instance.process.terminate()
                    try:
                        instance.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        instance.process.kill()
                
                instance.status = ServerStatus.STOPPED
                instance.process = None
                
                # Update database
                server_config = Database.get_mcp_server(name=server_name)
                if server_config:
                    Database.update_mcp_server(
                        server_config["id"],
                        is_connected=False
                    )
                
                print(f"[MCPManager] Server stopped: {server_name}")
                return True
                
            except Exception as e:
                instance.status = ServerStatus.ERROR
                instance.last_error = f"Stop failed: {e}"
                return False
    
    def restart_server(self, server_name: str) -> bool:
        """Restart an MCP server"""
        print(f"[MCPManager] Restarting server: {server_name}")
        self.stop_server(server_name)
        time.sleep(self._restart_delay_seconds)
        return self.start_server(server_name)
    
    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call a tool on an MCP server.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments
        
        Returns:
            dict with 'success', 'result', 'error' keys
        """
        with self._lock:
            if server_name not in self._servers:
                # Try to start the server
                if not self.start_server(server_name):
                    return {"success": False, "error": "Server not running"}
            
            instance = self._servers[server_name]
            
            if instance.status != ServerStatus.RUNNING:
                return {"success": False, "error": f"Server status: {instance.status}"}
            
            config = instance.config
            transport = config.get("transport", "stdio")
            
            if transport == "stdio":
                return self._call_stdio_tool(instance, tool_name, arguments)
            elif transport == "http":
                return self._call_http_tool(instance, tool_name, arguments)
            else:
                return {"success": False, "error": f"Unknown transport: {transport}"}
    
    def _call_stdio_tool(
        self,
        instance: MCPServerInstance,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call tool via stdio"""
        if not instance.process:
            return {"success": False, "error": "No process"}
        
        try:
            request = {
                "jsonrpc": "2.0",
                "id": f"call_{tool_name}",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            instance.process.stdin.write(json.dumps(request) + "\n")
            instance.process.stdin.flush()
            
            # Read response
            response_line = instance.process.stdout.readline()
            if not response_line:
                return {"success": False, "error": "No response"}
            
            response = json.loads(response_line)
            
            if "error" in response:
                return {"success": False, "error": response["error"].get("message", "Tool error")}
            
            return {"success": True, "result": response.get("result", {})}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _call_http_tool(
        self,
        instance: MCPServerInstance,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call tool via HTTP"""
        url = instance.config.get("url")
        if not url:
            return {"success": False, "error": "No URL"}
        
        try:
            import requests
            
            request = {
                "jsonrpc": "2.0",
                "id": f"call_{tool_name}",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            response = requests.post(
                url,
                json=request,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            data = response.json()
            
            if "error" in data:
                return {"success": False, "error": data["error"].get("message", "Tool error")}
            
            return {"success": True, "result": data.get("result", {})}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_server_status(self, server_name: str) -> Dict[str, Any]:
        """Get status of an MCP server"""
        with self._lock:
            if server_name not in self._servers:
                # Check database for config
                config = Database.get_mcp_server(name=server_name)
                if not config:
                    return {"exists": False}
                
                return {
                    "exists": True,
                    "status": ServerStatus.STOPPED.value,
                    "config": config
                }
            
            instance = self._servers[server_name]
            return {
                "exists": True,
                "status": instance.status.value,
                "config": instance.config,
                "tools": [
                    {"name": t.name, "description": t.description}
                    for t in instance.tools
                ],
                "last_error": instance.last_error,
                "connection_count": instance.connection_count
            }
    
    def get_server(self, server_name: str) -> Optional[MCPServerInstance]:
        """Get a running MCP server instance"""
        with self._lock:
            return self._servers.get(server_name)
    
    def list_servers(self) -> List[Dict[str, Any]]:
        """List all MCP servers and their status"""
        result = []
        
        # Get all servers from database
        servers = Database.list_mcp_servers()
        
        for server in servers:
            server_name = server["name"]
            status_info = self.get_server_status(server_name)
            
            result.append({
                "name": server_name,
                "id": server["id"],
                "transport": server.get("transport", "stdio"),
                "is_active": server["is_active"],
                "status": status_info.get("status", "unknown"),
                "last_error": server.get("last_error")
            })
        
        return result
    
    def get_all_tools(self) -> List[MCPTool]:
        """Get all available tools from all running MCP servers"""
        tools = []
        
        with self._lock:
            for name, instance in self._servers.items():
                if instance.status == ServerStatus.RUNNING:
                    tools.extend(instance.tools)
        
        return tools
    
    def shutdown(self):
        """Shutdown all MCP servers"""
        with self._lock:
            for server_name in list(self._servers.keys()):
                self.stop_server(server_name)


# Singleton instance
_mcp_manager = None

def get_mcp_manager() -> MCPManager:
    """Get or create MCPManager singleton"""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
    return _mcp_manager
