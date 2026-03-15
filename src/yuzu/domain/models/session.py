"""Session domain models."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class SessionMemory:
    """Memory/context for a specific session."""
    context: str = ""
    last_summarized: Optional[datetime] = None
    summary_count: int = 0
    
    def needs_summarization(self, message_count: int) -> bool:
        """Check if session needs summarization."""
        if self.summary_count == 0:
            return message_count >= 10
        return message_count >= 25


@dataclass
class ChatSession:
    """Chat session aggregate root."""
    id: int
    name: str
    is_active: bool = False
    message_count: int = 0
    memory: SessionMemory = field(default_factory=SessionMemory)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def activate(self) -> None:
        """Mark session as active."""
        self.is_active = True
        self.updated_at = datetime.now()
    
    def deactivate(self) -> None:
        """Mark session as inactive."""
        self.is_active = False
        self.updated_at = datetime.now()
    
    def increment_message_count(self) -> int:
        """Increment message count and return new count."""
        self.message_count += 1
        self.updated_at = datetime.now()
        return self.message_count
    
    def rename(self, new_name: str) -> None:
        """Rename the session."""
        self.name = new_name
        self.updated_at = datetime.now()
