"""Pytest configuration and fixtures."""

import pytest
from datetime import datetime

# Add src to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from yuzu.domain.models import (
    Profile, UserPreferences, PartnerProfile,
    ChatSession, SessionMemory,
    Message, MessageRole,
)


@pytest.fixture
def user_preferences():
    """Sample user preferences."""
    return UserPreferences(
        providers_config={"preferred_provider": "ollama"},
        preferred_provider="ollama",
        streaming_enabled=False,
    )


@pytest.fixture
def partner_profile():
    """Sample partner profile."""
    return PartnerProfile(
        name="Yuzu",
        relationship_stage="close",
        personality="friendly, helpful",
    )


@pytest.fixture
def sample_profile(user_preferences, partner_profile):
    """Sample profile for testing."""
    return Profile(
        id=1,
        display_name="TestUser",
        preferences=user_preferences,
        partner=partner_profile,
        affection=75,
    )


@pytest.fixture
def sample_session():
    """Sample chat session for testing."""
    return ChatSession(
        id=1,
        name="Test Session",
        is_active=True,
        message_count=10,
    )


@pytest.fixture
def sample_message():
    """Sample message for testing."""
    return Message(
        id=1,
        session_id=1,
        role=MessageRole.USER,
        content="Hello, how are you?",
    )
