"""Message domain models."""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


class MessageRole(Enum):
    """Message roles in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    # Tool-specific roles
    IMAGE_TOOLS = "image_tools"
    REQUEST_TOOLS = "request_tools"
    MEMORY_SEARCH_TOOLS = "memory_search_tools"
    MEMORY_SQL_TOOLS = "memory_sql_tools"
    
    @classmethod
    def is_tool_role(cls, role: str) -> bool:
        """Check if role is a tool role."""
        return role.endswith("_tools") or role == "tool"


@dataclass
class Message:
    """Chat message entity."""
    id: int
    session_id: int
    role: MessageRole
    content: Any  # str or list for multimodal
    timestamp: datetime = field(default_factory=datetime.now)
    image_paths: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_from_user(self) -> bool:
        """Check if message is from user."""
        return self.role == MessageRole.USER
    
    @property
    def is_from_assistant(self) -> bool:
        """Check if message is from assistant."""
        return self.role == MessageRole.ASSISTANT
    
    @property
    def is_tool_result(self) -> bool:
        """Check if message is a tool result."""
        return MessageRole.is_tool_role(self.role.value)
    
    def to_llm_format(self) -> Dict[str, Any]:
        """Convert to LLM API format."""
        return {
            "role": self.role.value,
            "content": self.content,
        }
