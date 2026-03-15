"""Tool domain models."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ToolExecutionStatus(Enum):
    """Tool execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class ToolCall:
    """A tool call request."""
    tool_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    detected_from_message: Optional[str] = None
    confidence: float = 1.0


@dataclass
class ToolResult:
    """Result of tool execution."""
    tool_name: str
    status: ToolExecutionStatus
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    @property
    def is_success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ToolExecutionStatus.SUCCESS
    
    @property
    def is_error(self) -> bool:
        """Check if execution failed."""
        return self.status == ToolExecutionStatus.ERROR
    
    def complete(self) -> None:
        """Mark as completed."""
        self.completed_at = datetime.now()
