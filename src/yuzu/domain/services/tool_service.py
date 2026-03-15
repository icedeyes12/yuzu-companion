"""Tool domain service - Tool execution orchestration.

Manages tool discovery, execution, and result formatting.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum

from ...domain.interfaces import ToolRegistry, ToolExecutor


class ToolType(Enum):
    """Types of tools."""
    INTERNAL = "internal"
    MCP_STDIO = "mcp_stdio"
    MCP_HTTP = "mcp_http"


@dataclass
class ToolDefinition:
    """Definition of a tool."""
    name: str
    description: str
    type: ToolType
    executor: Optional[Callable] = None
    requires_confirmation: bool = False


@dataclass
class ToolExecution:
    """Result of tool execution."""
    tool_name: str
    is_success: bool
    raw_result: Any
    formatted_output: str
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolService:
    """Tool domain service.
    
    Responsibilities:
    - Tool discovery and registration
    - Tool execution orchestration
    - Result formatting
    - MCP server management
    """
    
    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        internal_tools: Optional[Dict[str, Callable]] = None,
    ):
        self._registry = tool_registry
        self._internal_tools = internal_tools or {}
        self._mcp_servers: Dict[str, Any] = {}
    
    def get_available_tools(self) -> List[ToolDefinition]:
        """Get all available tools."""
        tools = []
        
        # Internal tools
        for name, executor in self._internal_tools.items():
            tools.append(ToolDefinition(
                name=name,
                description=getattr(executor, "__doc__", "No description"),
                type=ToolType.INTERNAL,
            ))
        
        # MCP tools (from registry)
        if self._registry:
            for tool in self._registry.list_tools():
                tools.append(ToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    type=ToolType(tool.type),
                ))
        
        return tools
    
    def execute(
        self,
        tool_name: str,
        args: str,
        session_id: int,
        **kwargs
    ) -> ToolExecution:
        """Execute a tool."""
        # Check internal tools first
        if tool_name in self._internal_tools:
            return self._execute_internal(tool_name, args, session_id)
        
        # Check MCP registry
        if self._registry and self._registry.has_tool(tool_name):
            return self._execute_mcp(tool_name, args, session_id)
        
        # Unknown tool
        return ToolExecution(
            tool_name=tool_name,
            is_success=False,
            raw_result=None,
            formatted_output=f"Error: Unknown tool '{tool_name}'",
            error_message=f"Tool not found: {tool_name}",
        )
    
    def _execute_internal(
        self, tool_name: str, args: str, session_id: int
    ) -> ToolExecution:
        """Execute internal tool."""
        executor = self._internal_tools[tool_name]
        
        try:
            # Parse arguments
            parsed_args = self._parse_args(tool_name, args)
            
            # Execute
            result = executor(parsed_args, session_id=session_id)
            
            return ToolExecution(
                tool_name=tool_name,
                is_success=True,
                raw_result=result,
                formatted_output=result,
            )
        except Exception as e:
            return ToolExecution(
                tool_name=tool_name,
                is_success=False,
                raw_result=None,
                formatted_output=f"Error: {str(e)}",
                error_message=str(e),
            )
    
    def _execute_mcp(
        self, tool_name: str, args: str, session_id: int
    ) -> ToolExecution:
        """Execute MCP tool."""
        if not self._registry:
            return ToolExecution(
                tool_name=tool_name,
                is_success=False,
                raw_result=None,
                formatted_output="Error: MCP registry not available",
                error_message="MCP registry not available",
            )
        
        try:
            result = self._registry.execute(tool_name, args)
            return ToolExecution(
                tool_name=tool_name,
                is_success=True,
                raw_result=result,
                formatted_output=str(result),
            )
        except Exception as e:
            return ToolExecution(
                tool_name=tool_name,
                is_success=False,
                raw_result=None,
                formatted_output=f"Error: {str(e)}",
                error_message=str(e),
            )
    
    def _parse_args(self, tool_name: str, args_str: str) -> Dict[str, Any]:
        """Parse tool arguments from string."""
        # Simple parsing - tools should parse their own args
        # For now, pass as "prompt" or "query" or "url"
        
        if tool_name in ("image_generate", "imagine"):
            return {"prompt": args_str}
        elif tool_name == "request":
            return {"url": args_str}
        elif tool_name in ("memory_search", "memory_sql"):
            return {"query": args_str}
        else:
            return {"args": args_str}
    
    def register_internal_tool(
        self, name: str, executor: Callable, description: str = ""
    ) -> None:
        """Register an internal tool."""
        executor.__doc__ = description or executor.__doc__
        self._internal_tools[name] = executor
    
    def detect_tool_intent(self, message: str) -> Optional[str]:
        """Detect if message contains tool intent."""
        message_lower = message.lower().strip()
        
        # Command prefix
        if message.strip().startswith("/"):
            parts = message.strip().split(None, 1)
            cmd = parts[0][1:]
            if cmd in self._internal_tools:
                return cmd
        
        # Keyword detection
        image_keywords = [
            "generate", "create image", "draw", "imagine", "buat gambar",
            "gambar", "picture", "photo", "make image", "draw image"
        ]
        for kw in image_keywords:
            if kw in message_lower:
                return "image_generate"
        
        return None
