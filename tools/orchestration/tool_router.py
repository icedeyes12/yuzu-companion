# Tool Router Module
# Routes tool execution to internal tools or MCP servers

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
from enum import Enum
from datetime import datetime
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from database import Database
from ..registry import execute_tool as execute_internal_tool


class ToolType(Enum):
    """Types of tools available."""
    INTERNAL = "internal"  # Native yuzu tools (image_generate, etc.)
    MCP = "mcp"           # External MCP servers


@dataclass
class ToolResult:
    """Result of tool execution."""
    tool_type: ToolType
    tool_name: str
    status: str  # success, error, timeout
    result: Any = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    execution_id: Optional[int] = None  # Database ID for tracking
    display_data: Dict[str, Any] = field(default_factory=dict)  # Formatted for UI


class ToolRouter:
    """
    Routes tool execution to appropriate handler.
    
    Handles both internal tools and MCP server connections.
    Manages timeouts and error handling.
    """
    
    # Tool timeout configuration (seconds)
    TIMEOUTS = {
        'image_generate': 120,  # 2 minutes for image generation
        'web_search': 30,
        'weather': 30,
        'memory_search': 10,
        'memory_sql': 10,
        'http_request': 60,
        'mcp_default': 30,
    }
    
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._active_mcp_connections: Dict[str, Any] = {}  # name -> connection
        self._tool_type_cache: Dict[str, ToolType] = {}  # tool_name -> type
    
    def route(self, tool_name: str, params: Dict[str, Any], 
              session_id: int, message_id: Optional[int] = None,
              mcp_server: Optional[str] = None) -> ToolResult:
        """
        Route tool execution.
        
        Args:
            tool_name: Name of the tool to execute
            params: Tool parameters
            session_id: Current chat session ID
            message_id: Optional parent message ID
            mcp_server: Optional MCP server name (for MCP tools)
            
        Returns:
            ToolResult with execution outcome
        """
        start_time = datetime.now()
        
        # Determine tool type
        if mcp_server:
            tool_type = ToolType.MCP
        else:
            tool_type = self._get_tool_type(tool_name)
        
        # Create execution record
        execution_id = Database.create_tool_execution(
            session_id=session_id,
            tool_type=tool_type.value,
            tool_name=tool_name,
            input_params=params,
            message_id=message_id
        )
        
        try:
            # Update status to running
            Database.update_tool_execution_status(execution_id, 'running')
            
            # Execute based on type
            if tool_type == ToolType.INTERNAL:
                result = self._execute_internal(tool_name, params, session_id, execution_id)
            elif tool_type == ToolType.MCP:
                result = self._execute_mcp(tool_name, params, mcp_server, execution_id)
            else:
                raise ValueError(f"Unknown tool type: {tool_type}")
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Update database with success
            Database.complete_tool_execution(
                execution_id,
                output_result={'result': result, 'display': self._format_for_display(tool_name, result)}
            )
            
            return ToolResult(
                tool_type=tool_type,
                tool_name=tool_name,
                status='success',
                result=result,
                execution_time_ms=execution_time,
                execution_id=execution_id,
                display_data=self._format_for_display(tool_name, result)
            )
            
        except FutureTimeoutError:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            Database.complete_tool_execution(
                execution_id,
                error_message="Tool execution timed out"
            )
            
            return ToolResult(
                tool_type=tool_type,
                tool_name=tool_name,
                status='timeout',
                error_message=f"Tool '{tool_name}' timed out after {self.TIMEOUTS.get(tool_name, 30)}s",
                execution_time_ms=execution_time,
                execution_id=execution_id,
                display_data={'error': 'timeout', 'message': 'Tool execution timed out'}
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            Database.complete_tool_execution(
                execution_id,
                error_message=str(e)
            )
            
            return ToolResult(
                tool_type=tool_type,
                tool_name=tool_name,
                status='error',
                error_message=str(e),
                execution_time_ms=execution_time,
                execution_id=execution_id,
                display_data={'error': 'execution_failed', 'message': str(e)}
            )
    
    def _get_tool_type(self, tool_name: str) -> ToolType:
        """Determine if tool is internal or MCP."""
        # Check cache
        if tool_name in self._tool_type_cache:
            return self._tool_type_cache[tool_name]
        
        # List of internal tools
        internal_tools = {
            'image_generate', 'imagine', 'web_search', 'weather',
            'memory_search', 'memory_sql', 'http_request', 'request'
        }
        
        if tool_name in internal_tools or tool_name.startswith('imagine'):
            tool_type = ToolType.INTERNAL
        else:
            # Check if it's registered as an MCP tool
            mcp_servers = Database.list_mcp_servers(active_only=True)
            if any(tool_name == s['name'] or tool_name.startswith(s['name']) 
                   for s in mcp_servers):
                tool_type = ToolType.MCP
            else:
                # Default to internal for unknown tools
                tool_type = ToolType.INTERNAL
        
        self._tool_type_cache[tool_name] = tool_type
        return tool_type
    
    def _execute_internal(self, tool_name: str, params: Dict, 
                          session_id: int, execution_id: int) -> Any:
        """Execute internal tool with timeout."""
        timeout = self.TIMEOUTS.get(tool_name, 30)
        
        # Submit to thread pool
        future = self._executor.submit(
            execute_internal_tool,
            tool_name,
            params,
            session_id
        )
        
        # Wait with timeout
        return future.result(timeout=timeout)
    
    def _execute_mcp(self, tool_name: str, params: Dict, 
                     mcp_server_name: str, execution_id: int) -> Any:
        """Execute MCP tool via server connection."""
        # Get server configuration
        server = Database.get_mcp_server(name=mcp_server_name)
        if not server:
            raise ValueError(f"MCP server '{mcp_server_name}' not found")
        
        if not server['is_active']:
            raise ValueError(f"MCP server '{mcp_server_name}' is inactive")
        
        # Get or create connection
        connection = self._get_mcp_connection(mcp_server_name)
        
        # Execute tool via MCP protocol
        timeout = self.TIMEOUTS.get('mcp_default', 30)
        
        future = self._executor.submit(
            self._call_mcp_tool,
            connection,
            tool_name,
            params
        )
        
        return future.result(timeout=timeout)
    
    def _get_mcp_connection(self, server_name: str) -> Any:
        """Get or establish MCP server connection."""
        if server_name in self._active_mcp_connections:
            return self._active_mcp_connections[server_name]
        
        # Get server config
        server = Database.get_mcp_server(name=server_name)
        if not server:
            raise ValueError(f"MCP server '{server_name}' not found")
        
        # Establish connection based on transport
        if server['transport'] == 'stdio':
            connection = self._connect_stdio_mcp(server)
        elif server['transport'] == 'http':
            connection = self._connect_http_mcp(server)
        else:
            raise ValueError(f"Unknown MCP transport: {server['transport']}")
        
        self._active_mcp_connections[server_name] = connection
        
        # Update server status
        Database.update_mcp_server(server['id'], is_connected=True)
        
        return connection
    
    def _connect_stdio_mcp(self, server: Dict) -> Any:
        """Connect to stdio-based MCP server."""
        # This is a placeholder - stdio MCP requires subprocess management
        # Would use subprocess.Popen to start the server process
        # and communicate via stdin/stdout
        raise NotImplementedError("stdio MCP connection not yet implemented")
    
    def _connect_http_mcp(self, server: Dict) -> Any:
        """Connect to HTTP-based MCP server."""
        # This is a placeholder - HTTP MCP would use requests
        # to communicate with the server
        raise NotImplementedError("HTTP MCP connection not yet implemented")
    
    def _call_mcp_tool(self, connection: Any, tool_name: str, params: Dict) -> Any:
        """Call a tool via MCP connection."""
        # Placeholder for actual MCP protocol call
        # Would use JSON-RPC or similar protocol
        raise NotImplementedError("MCP tool calling not yet implemented")
    
    def _format_for_display(self, tool_name: str, result: Any) -> Dict[str, Any]:
        """Format tool result for UI display."""
        display = {
            'tool_name': tool_name,
            'tool_icon': self._get_tool_icon(tool_name),
            'status': 'success'
        }
        
        if tool_name in ('image_generate', 'imagine'):
            # Handle image result
            if isinstance(result, str) and result.endswith(('.png', '.jpg', '.jpeg')):
                display['type'] = 'image'
                display['image_url'] = result
                display['image_alt'] = 'Generated image'
            elif isinstance(result, dict) and 'image_path' in result:
                display['type'] = 'image'
                display['image_url'] = result['image_path']
                display['image_alt'] = result.get('prompt', 'Generated image')[:50]
            else:
                display['type'] = 'text'
                display['text'] = str(result)
                
        elif tool_name == 'weather':
            display['type'] = 'weather_card'
            display['weather_data'] = result if isinstance(result, dict) else {'description': str(result)}
            
        elif tool_name == 'web_search':
            display['type'] = 'search_results'
            display['results'] = result if isinstance(result, list) else [{'title': 'Result', 'content': str(result)}]
            
        else:
            # Default text display
            display['type'] = 'text'
            if isinstance(result, dict):
                display['text'] = json.dumps(result, indent=2)
            else:
                display['text'] = str(result)
        
        return display
    
    def _get_tool_icon(self, tool_name: str) -> str:
        """Get icon for tool."""
        icons = {
            'image_generate': '🖼️',
            'imagine': '🖼️',
            'web_search': '🔍',
            'weather': '🌤️',
            'memory_search': '🧠',
            'memory_sql': '🧠',
            'http_request': '🌐',
            'request': '🌐',
        }
        return icons.get(tool_name, '🔧')
    
    def list_available_tools(self, include_mcp: bool = True) -> List[Dict]:
        """List all available tools."""
        tools = []
        
        # Internal tools
        internal_tools = [
            {'name': 'image_generate', 'type': 'internal', 'icon': '🖼️', 
             'description': 'Generate images from text descriptions'},
            {'name': 'web_search', 'type': 'internal', 'icon': '🔍',
             'description': 'Search the web for current information'},
            {'name': 'weather', 'type': 'internal', 'icon': '🌤️',
             'description': 'Get current weather information'},
            {'name': 'memory_search', 'type': 'internal', 'icon': '🧠',
             'description': 'Search conversation memory'},
            {'name': 'http_request', 'type': 'internal', 'icon': '🌐',
             'description': 'Make HTTP requests to APIs'},
        ]
        tools.extend(internal_tools)
        
        # MCP tools
        if include_mcp:
            mcp_servers = Database.list_mcp_servers(active_only=True)
            for server in mcp_servers:
                tools.append({
                    'name': server['name'],
                    'type': 'mcp',
                    'icon': '🔌',
                    'description': f'MCP server ({server["transport"]})',
                    'connected': server['is_connected']
                })
        
        return tools
    
    def close(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False)
        # Close MCP connections
        for name, conn in self._active_mcp_connections.items():
            try:
                server = Database.get_mcp_server(name=name)
                if server:
                    Database.update_mcp_server(server['id'], is_connected=False)
            except:
                pass
        self._active_mcp_connections.clear()
