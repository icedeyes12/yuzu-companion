"""Domain models - Core business entities.

These are pure dataclasses with no external dependencies.
They represent the core business concepts of the application.
"""

from .user import Profile, PartnerProfile, UserPreferences, ApiKeys
from .session import ChatSession, SessionMemory
from .message import Message, MessageRole
from .memory import MemoryFact, EpisodicMemory, MemoryType
from .tool import ToolCall, ToolResult, ToolExecutionStatus

__all__ = [
    # User
    "Profile",
    "PartnerProfile",
    "UserPreferences",
    "ApiKeys",
    # Session
    "ChatSession",
    "SessionMemory",
    # Message
    "Message",
    "MessageRole",
    # Memory
    "MemoryFact",
    "EpisodicMemory",
    "MemoryType",
    # Tool
    "ToolCall",
    "ToolResult",
    "ToolExecutionStatus",
]
