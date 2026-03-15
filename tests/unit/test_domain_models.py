"""Unit tests for domain models."""

import pytest
from datetime import datetime

from yuzu.domain.models import (
    Profile, UserPreferences, PartnerProfile,
    ChatSession, SessionMemory,
    Message, MessageRole,
)


class TestProfile:
    """Test Profile domain model."""

    def test_profile_creation(self, sample_profile):
        """Test profile can be created with required fields."""
        assert sample_profile.id == 1
        assert sample_profile.display_name == "TestUser"
        assert sample_profile.affection == 75
        assert sample_profile.partner.name == "Yuzu"

    def test_update_affection(self, sample_profile):
        """Test affection update with clamping."""
        assert sample_profile.update_affection(10) == 85
        assert sample_profile.update_affection(20) == 100
        sample_profile.affection = 50
        assert sample_profile.update_affection(-10) == 40
        assert sample_profile.update_affection(-100) == 0

    def test_get_preferred_provider(self, sample_profile):
        """Test getting preferred provider."""
        assert sample_profile.get_preferred_provider() == "ollama"


class TestChatSession:
    """Test ChatSession domain model."""

    def test_session_creation(self, sample_session):
        """Test session can be created."""
        assert sample_session.id == 1
        assert sample_session.name == "Test Session"
        assert sample_session.is_active is True

    def test_increment_message_count(self, sample_session):
        """Test message count increments."""
        initial = sample_session.message_count
        new_count = sample_session.increment_message_count()
        assert new_count == initial + 1

    def test_rename(self, sample_session):
        """Test session rename."""
        sample_session.rename("New Name")
        assert sample_session.name == "New Name"


class TestMessage:
    """Test Message domain model."""

    def test_message_creation(self, sample_message):
        """Test message can be created."""
        assert sample_message.id == 1
        assert sample_message.role == MessageRole.USER

    def test_is_from_user(self, sample_message):
        """Test is_from_user check."""
        assert sample_message.is_from_user is True
        assert sample_message.is_from_assistant is False

    def test_is_tool_result(self):
        """Test tool role detection."""
        from yuzu.domain.models.message import Message, MessageRole
        tool_msg = Message(
            id=2, session_id=1,
            role=MessageRole.IMAGE_TOOLS,
            content="image result",
        )
        assert tool_msg.is_tool_result is True
