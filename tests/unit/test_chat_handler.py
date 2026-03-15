"""Unit tests for ChatHandler application handler."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))) + '/src')

from yuzu.application.handlers.chat_handler import (
    ChatHandler,
    handle_user_message,
    handle_user_message_streaming,
)


class TestChatHandler:
    """Test ChatHandler core functionality."""

    @pytest.fixture
    def handler(self):
        return ChatHandler()

    def test_handler_creation(self, handler):
        """Test handler can be created."""
        assert handler is not None
        # ChatHandler doesn't store container, just uses it during init
        assert handler._chat_service is not None
        assert handler._tool_service is not None

    def test_handle_message_simple(self, handler):
        """Test simple message handling (non-tool)."""
        # This will go through the handler
        # Should not crash even if AI is not available
        response = handler.handle_message(
            user_message="Hello",
            interface="terminal"
        )
        # Response should be a string (error message or actual response)
        assert isinstance(response, str)

    def test_handle_message_tool_command(self, handler):
        """Test that tool commands are detected."""
        result = handler._tool_service.detect_tool_intent("/imagine a cat")
        assert result is not None
        assert result == "image_generate"

    def test_detect_tool_intent_regular_message(self, handler):
        """Test regular messages don't trigger tool detection."""
        result = handler._tool_service.detect_tool_intent("Hello, how are you?")
        assert result is None

    def test_tool_detection_with_slash(self, handler):
        """Test various slash commands."""
        # Only test commands that are actually registered
        test_cases = [
            ("/imagine a dog", "image_generate"),
            ("/image_generate dog", "image_generate"),
        ]
        
        for message, expected_tool in test_cases:
            result = handler._tool_service.detect_tool_intent(message)
            assert result is not None
            assert result == expected_tool


class TestHandlerSingleton:
    """Test handler singleton pattern."""

    def test_get_chat_handler(self):
        """Test get_chat_handler returns singleton."""
        from yuzu.application.handlers.chat_handler import get_chat_handler, _handler_instance
        
        handler1 = get_chat_handler()
        handler2 = get_chat_handler()
        
        assert handler1 is handler2
        assert _handler_instance is not None
