"""Memory domain models."""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MemoryType(Enum):
    """Types of memory."""
    SEMANTIC = "semantic"  # Facts
    EPISODIC = "episodic"  # Events/experiences
    PROCEDURAL = "procedural"  # How to do things


@dataclass
class MemoryFact:
    """A semantic memory fact."""
    id: int
    entity: str
    relation: str
    target: str
    confidence: float = 0.5
    importance: float = 0.5
    session_id: Optional[int] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    
    def access(self) -> None:
        """Record an access to this memory."""
        self.access_count += 1
        self.last_accessed = datetime.now()


@dataclass
class EpisodicMemory:
    """An episodic memory (an event/experience)."""
    id: int
    summary: str
    importance: float = 0.5
    emotional_weight: float = 0.0
    session_id: Optional[int] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    
    def access(self) -> None:
        """Record an access to this memory."""
        self.access_count += 1
        self.last_accessed = datetime.now()
