"""Integration tests for SQLAlchemy repositories.

Tests that repositories correctly adapt from legacy database.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'src'))

from yuzu.infrastructure.config.container import get_container, reset_container
from yuzu.domain.models import Message, MessageRole


@pytest.fixture(autouse=True)
def reset_di_container():
    """Reset DI container before each test."""
    reset_container()
    yield


class TestRepositories:
    """Test repository implementations."""
    
    def test_container_repositories(self):
        """Test that repositories can be retrieved from container."""
        container = get_container()
        
        # Repositories should be accessible
        profile_repo = container.profile_repository
        session_repo = container.session_repository
        message_repo = container.message_repository
        
        assert profile_repo is not None
        assert session_repo is not None
        assert message_repo is not None
    
    
    def test_profile_repository_get(self):
        """Test getting profile through repository."""
        container = get_container()
        repo = container.profile_repository
        
        # Should return profile or None (no error)
        profile = repo.get()
        # Profile may or may not exist depending on database state
        if profile:
            assert profile.id is not None
            assert profile.display_name is not None
    
    
    def test_session_repository_get_active(self):
        """Test getting active session."""
        container = get_container()
        repo = container.session_repository
        
        # Should return session or None (no error)
        session = repo.get_active()
        # Session may or may not exist
        if session:
            assert session.id is not None
            assert session.name is not None
    
    
    def test_message_repository_get_history(self):
        """Test getting message history."""
        container = get_container()
        repo = container.message_repository
        
        # Try to get history for a non-existent session (should return empty list)
        history = repo.get_history(session_id=999999, limit=10)
        assert isinstance(history, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
