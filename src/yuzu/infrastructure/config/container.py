"""Dependency Injection Container.

Manual DI container - no framework dependency.
Provides lazy initialization and singleton management.
"""

from typing import Optional, Dict, Any, Callable
import os

# Domain interfaces
from ...domain.interfaces import (
    ProfileRepository,
    SessionRepository,
    MessageRepository,
    APIKeyRepository,
    UnitOfWork,
    AIProvider,
    ProviderRegistry,
)

# Infrastructure implementations
from ..db.repositories.profile_repository import SQLAlchemyProfileRepository
from ..db.repositories.session_repository import SQLAlchemySessionRepository
from ..db.repositories.message_repository import SQLAlchemyMessageRepository


class FeatureFlags:
    """Feature flags for gradual migration."""
    
    # Set via environment variables
    USE_NEW_DATABASE = os.getenv('YUZU_USE_NEW_DB', 'false').lower() == 'true'
    USE_NEW_PROVIDERS = os.getenv('YUZU_USE_NEW_PROVIDERS', 'false').lower() == 'true'
    USE_NEW_TOOLS = os.getenv('YUZU_USE_NEW_TOOLS', 'false').lower() == 'true'
    USE_NEW_CHAT_HANDLER = os.getenv('YUZU_USE_NEW_CHAT', 'false').lower() == 'true'
    
    # Debug mode
    DEBUG = os.getenv('YUZU_DEBUG', 'false').lower() == 'true'


class Container:
    """Manual DI container."""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._init_factories()
    
    def _init_factories(self):
        """Register factory methods for lazy initialization."""
        
        # Repositories
        self._factories['profile_repo'] = lambda: SQLAlchemyProfileRepository()
        self._factories['session_repo'] = lambda: SQLAlchemySessionRepository()
        self._factories['message_repo'] = lambda: SQLAlchemyMessageRepository()
        
        # Placeholder for AI providers (will be implemented in Phase 2/3)
        self._factories['provider_registry'] = lambda: None  # Will be implemented
    
    def get(self, name: str) -> Any:
        """Get service by name (lazy initialization)."""
        if name not in self._services:
            if name in self._factories:
                self._services[name] = self._factories[name]()
            else:
                raise KeyError(f"Service not registered: {name}")
        return self._services[name]
    
    # Repository accessors
    
    @property
    def profile_repository(self) -> ProfileRepository:
        """Get profile repository."""
        return self.get('profile_repo')
    
    @property
    def session_repository(self) -> SessionRepository:
        """Get session repository."""
        return self.get('session_repo')
    
    @property
    def message_repository(self) -> MessageRepository:
        """Get message repository."""
        return self.get('message_repo')
    
    @property
    def provider_registry(self) -> Optional[ProviderRegistry]:
        """Get provider registry (if new implementation enabled)."""
        if FeatureFlags.USE_NEW_PROVIDERS:
            return self.get('provider_registry')
        return None
    
    def reset(self) -> None:
        """Reset all services (for testing)."""
        self._services.clear()


# Global container instance
_container: Optional[Container] = None


def get_container() -> Container:
    """Get the global container instance."""
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Reset the global container (for testing)."""
    global _container
    _container = None
