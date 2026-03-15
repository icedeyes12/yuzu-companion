"""Database repository interfaces (Ports).

These abstract classes define the contract for all database operations.
Implementations are in infrastructure/db/repositories/.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Protocol
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Profile:
    """Domain entity for user profile."""
    id: int
    display_name: str
    partner_name: str
    affection: int
    theme: str
    memory: Dict[str, Any]
    session_history: Dict[str, Any]
    global_knowledge: Dict[str, Any]
    providers_config: Dict[str, Any]
    context: Dict[str, Any]
    image_model: str
    vision_model: str
    created_at: datetime
    updated_at: datetime


@dataclass
class ChatSession:
    """Domain entity for chat session."""
    id: int
    name: str
    is_active: bool
    message_count: int
    memory: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class Message:
    """Domain entity for chat message."""
    id: int
    session_id: int
    role: str
    content: str
    timestamp: datetime
    image_paths: Optional[List[str]] = None


@dataclass
class APIKey:
    """Domain entity for API key."""
    id: int
    key_name: str
    key_value: str
    key_encrypted: bool
    created_at: datetime


class ProfileRepository(ABC):
    """Repository for Profile entity operations."""

    @abstractmethod
    def get(self) -> Optional[Profile]:
        """Get the current user profile."""
        pass

    @abstractmethod
    def update(self, profile: Profile) -> Profile:
        """Update and return the profile."""
        pass

    @abstractmethod
    def get_api_keys(self) -> Dict[str, str]:
        """Get all API keys as a dictionary."""
        pass

    @abstractmethod
    def update_api_keys(self, keys: Dict[str, str]) -> None:
        """Update API keys."""
        pass


class SessionRepository(ABC):
    """Repository for ChatSession entity operations."""

    @abstractmethod
    def get_active(self) -> Optional[ChatSession]:
        """Get the currently active session."""
        pass

    @abstractmethod
    def get_all(self) -> List[ChatSession]:
        """Get all sessions ordered by updated_at desc."""
        pass

    @abstractmethod
    def get_by_id(self, session_id: int) -> Optional[ChatSession]:
        """Get session by ID."""
        pass

    @abstractmethod
    def create(self, name: str) -> ChatSession:
        """Create a new session and return it."""
        pass

    @abstractmethod
    def update(self, session: ChatSession) -> ChatSession:
        """Update and return the session."""
        pass

    @abstractmethod
    def delete(self, session_id: int) -> bool:
        """Delete a session. Returns True if deleted."""
        pass

    @abstractmethod
    def switch_to(self, session_id: int) -> bool:
        """Switch active session. Returns True if successful."""
        pass


class MessageRepository(ABC):
    """Repository for Message entity operations."""

    @abstractmethod
    def get_history(
        self,
        session_id: int,
        limit: int = 50,
        include_tool_roles: bool = False,
    ) -> List[Message]:
        """Get chat history for a session."""
        pass

    @abstractmethod
    def add(self, message: Message) -> Message:
        """Add a message and return it with ID."""
        pass

    @abstractmethod
    def add_tool_result(
        self,
        session_id: int,
        tool_name: str,
        result_content: str,
    ) -> Message:
        """Add a tool result message."""
        pass

    @abstractmethod
    def clear_history(self, session_id: int) -> int:
        """Clear all messages for a session. Returns count deleted."""
        pass


class APIKeyRepository(ABC):
    """Repository for API key operations."""

    @abstractmethod
    def get(self, key_name: str) -> Optional[str]:
        """Get decrypted API key by name."""
        pass

    @abstractmethod
    def get_all(self) -> Dict[str, str]:
        """Get all API keys as dictionary."""
        pass

    @abstractmethod
    def save(self, key_name: str, key_value: str) -> None:
        """Save an API key (encrypted)."""
        pass


class UnitOfWork(ABC):
    """Unit of Work pattern for transaction management."""

    @abstractmethod
    def __enter__(self) -> "UnitOfWork":
        """Enter context manager."""
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager - commit or rollback."""
        pass

    @abstractmethod
    def commit(self) -> None:
        """Commit the current transaction."""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Rollback the current transaction."""
        pass

    @property
    @abstractmethod
    def profiles(self) -> ProfileRepository:
        """Get profile repository."""
        pass

    @property
    @abstractmethod
    def sessions(self) -> SessionRepository:
        """Get session repository."""
        pass

    @property
    @abstractmethod
    def messages(self) -> MessageRepository:
        """Get message repository."""
        pass

    @property
    @abstractmethod
    def api_keys(self) -> APIKeyRepository:
        """Get API key repository."""
        pass
