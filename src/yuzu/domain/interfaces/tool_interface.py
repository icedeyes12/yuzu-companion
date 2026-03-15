"""Tool execution interfaces (Ports).

Abstract contracts for tool execution (internal tools, MCP tools).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime


class ToolType(Enum):
    """Types of tools."""
    INTERNAL = "internal"
    MCP_STDIO = "mcp_stdio"
    MCP_HTTP = "mcp_http"


class ToolStatus(Enum):
    """Tool execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class ToolContext:
    """Context for tool execution."""
    session_id: int
    message_id: Optional[int] = None
    user_message: str = ""
    partner_name: str = "Yuzu"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of tool execution."""
    success: bool
    tool_name: str
    tool_type: ToolType
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    card_type: str = "text"  # For UI rendering

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "tool_type": self.tool_type.value,
            "output": self.output,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "card_type": self.card_type,
            "metadata": self.metadata,
        }


@dataclass
class ToolExecutionRecord:
    """Record of a tool execution (for database)."""
    id: int
    session_id: int
    message_id: Optional[int]
    tool_type: str
    tool_name: str
    status: str
    input_params: Dict[str, Any]
    output_result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class ToolExecutor(ABC):
    """Abstract base class for tool executors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass

    @property
    @abstractmethod
    def tool_type(self) -> ToolType:
        """Tool type."""
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate parameters. Returns (is_valid, error_message)."""
        pass


class ToolRegistry(ABC):
    """Registry for managing tools."""

    @abstractmethod
    def register(self, tool: ToolExecutor) -> None:
        """Register a tool."""
        pass

    @abstractmethod
    def get(self, name: str) -> Optional[ToolExecutor]:
        """Get tool by name."""
        pass

    @abstractmethod
    def list_tools(self) -> List[ToolExecutor]:
        """List all registered tools."""
        pass

    @abstractmethod
    def detect_intent(self, message: str) -> Optional[str]:
        """Detect if message should trigger a tool. Returns tool name or None."""
        pass


class ToolOrchestrator(ABC):
    """Orchestrates tool detection and execution."""

    @abstractmethod
    def detect_tool_need(self, message: str, context: ToolContext) -> Optional[str]:
        """Detect if a tool is needed for this message."""
        pass

    @abstractmethod
    def execute_tool(
        self, tool_name: str, params: Dict[str, Any], context: ToolContext
    ) -> ToolResult:
        """Execute a tool and return result."""
        pass

    @abstractmethod
    def format_result_for_llm(self, result: ToolResult) -> str:
        """Format tool result for LLM consumption."""
        pass

    @abstractmethod
    def format_result_for_ui(self, result: ToolResult) -> Dict[str, Any]:
        """Format tool result for UI rendering."""
        pass
