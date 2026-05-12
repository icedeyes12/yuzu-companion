"""
Unit tests for v3.1.0 Phase 4: Orchestrator Single Path Flow.

Tests for:
- Tool execution flow with DB verification
- No tool flow (plain response)
- Synthesis after tool execution
- Tool result storage with universal role
- First pass storage before tool execution
"""

from __future__ import annotations

import pytest


class TestOrchestratorSinglePath:
    """Test orchestrator single path execution."""

    def test_handle_user_message_returns_string(self):
        """handle_user_message returns a string response."""
        from app.orchestrator import handle_user_message
        
        response = handle_user_message("Hello")
        
        assert isinstance(response, str)
        assert len(response) > 0

    def test_handle_user_message_empty_returns_error(self):
        """Empty message returns error message."""
        from app.orchestrator import handle_user_message
        
        response = handle_user_message("")
        
        assert "enter a message" in response.lower()

    def test_handle_user_message_whitespace_returns_error(self):
        """Whitespace-only message returns error message."""
        from app.orchestrator import handle_user_message
        
        response = handle_user_message("   ")
        
        assert "enter a message" in response.lower()


class TestOrchestratorStreaming:
    """Test orchestrator streaming execution."""

    def test_handle_user_message_streaming_yields_strings(self):
        """handle_user_message_streaming yields string chunks."""
        from app.orchestrator import handle_user_message_streaming
        
        chunks = list(handle_user_message_streaming("Hello"))
        
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)

    def test_handle_user_message_streaming_empty_yields_error(self):
        """Empty message yields error message."""
        from app.orchestrator import handle_user_message_streaming
        
        chunks = list(handle_user_message_streaming(""))
        
        assert len(chunks) == 1
        assert "enter a message" in chunks[0].lower()


class TestImagineFastPath:
    """Test /imagine fast path execution."""

    def test_imagine_fast_path_executes_tool(self):
        """/imagine command executes tool directly."""
        from app.orchestrator import handle_user_message
        from app.database import Database
        
        # Get initial message count
        active_session = Database.get_active_session()
        session_id = active_session["id"]
        initial_count = Database.get_session_messages_count(session_id)
        
        response = handle_user_message("/imagine test image")
        
        # Should return some response
        assert isinstance(response, str)
        assert len(response) > 0
        
        # Should have added messages to DB
        final_count = Database.get_session_messages_count(session_id)
        assert final_count > initial_count

    def test_imagine_fast_path_empty_prompt_returns_error(self):
        """/imagine without prompt returns error message."""
        from app.orchestrator import handle_user_message
        
        response = handle_user_message("/imagine")
        
        assert "provide a prompt" in response.lower()


class TestToolResultStorage:
    """Test tool result storage with universal role."""

    def test_persist_tool_result_uses_universal_role(self):
        """_persist_tool_result stores with 'tools' role."""
        from app.orchestrator import _persist_tool_result
        from app.database import Database
        
        active_session = Database.get_active_session()
        session_id = active_session["id"]
        
        # Store a tool result
        _persist_tool_result(
            tool_name="memory_search",
            xml="<tool_result><name>memory_search</name><status>ok</status></tool_result>",
            markdown="<details>test</details>",
            session_id=session_id
        )
        
        # Verify it was stored with 'tools' role
        messages = Database.get_session_messages(session_id, limit=1)
        assert len(messages) > 0
        assert messages[0]["role"] == "tools"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
