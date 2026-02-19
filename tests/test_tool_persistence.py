"""Test tool result persistence in messages table."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_tool_result_persisted_in_chat_history():
    """Test that tool results stored via add_tool_result appear in get_chat_history."""
    from database import Database, Message, get_db_session

    active_session = Database.get_active_session()
    session_id = active_session['id']

    # Clear any existing messages
    Database.clear_chat_history(session_id=session_id)

    # Simulate the flow: user message → assistant command → tool result
    Database.add_message('user', 'What is the weather?', session_id=session_id)
    Database.add_message('assistant', '/weather Tokyo', session_id=session_id)
    Database.add_tool_result('weather', '{"temp": 25, "condition": "sunny"}', session_id=session_id)
    Database.add_message('assistant', 'The weather in Tokyo is sunny, 25°C!', session_id=session_id)

    # Verify tool result appears in chat history
    history = Database.get_chat_history(session_id=session_id)
    roles = [msg['role'] for msg in history]

    assert 'user' in roles, "User message not in history"
    assert 'assistant' in roles, "Assistant message not in history"
    assert 'tool' in roles, "Tool result not in chat history!"

    # Verify chronological order
    tool_idx = roles.index('tool')
    assert roles[0] == 'user', "First message should be user"
    assert roles[1] == 'assistant', "Second should be assistant command"
    assert roles[2] == 'tool', "Third should be tool result"
    assert roles[3] == 'assistant', "Fourth should be assistant response"
    print("✓ Tool results appear in get_chat_history in correct order")


def test_tool_result_in_ai_history():
    """Test that tool results appear in get_chat_history_for_ai."""
    from database import Database

    active_session = Database.get_active_session()
    session_id = active_session['id']

    Database.clear_chat_history(session_id=session_id)

    # Simulate full flow
    Database.add_message('user', 'Search for Python tutorials', session_id=session_id)
    Database.add_message('assistant', '/web_search Python tutorials', session_id=session_id)
    Database.add_tool_result('web_search', '{"results": [{"title": "Python Tutorial"}]}', session_id=session_id)
    Database.add_message('assistant', 'Here are some Python tutorials!', session_id=session_id)

    # Verify tool messages in AI history
    ai_history = Database.get_chat_history_for_ai(session_id=session_id)
    roles = [msg['role'] for msg in ai_history]

    assert 'tool' in roles, "Tool result not in AI history!"
    assert roles.count('assistant') == 2, "Should have 2 assistant messages"
    assert roles.count('tool') == 1, "Should have 1 tool message"
    print("✓ Tool results appear in get_chat_history_for_ai")


def test_tool_result_formatting():
    """Test that add_tool_result formats content correctly."""
    from database import Database, Message, get_db_session

    active_session = Database.get_active_session()
    session_id = active_session['id']

    Database.clear_chat_history(session_id=session_id)

    Database.add_tool_result('web_search', 'some result data', session_id=session_id)

    with get_db_session() as session:
        tool_msg = session.query(Message).filter(
            Message.session_id == session_id,
            Message.role == 'tool'
        ).first()

        assert tool_msg is not None, "Tool message not found"
        assert tool_msg.role == 'tool'
        assert '🔧 TOOL RESULT — WEB_SEARCH' in tool_msg.content
        assert 'some result data' in tool_msg.content
        assert tool_msg.content.endswith('---')
        print("✓ Tool result formatting is correct")


if __name__ == "__main__":
    try:
        test_tool_result_persisted_in_chat_history()
        test_tool_result_in_ai_history()
        test_tool_result_formatting()
        print("\n" + "=" * 50)
        print("✅ ALL TOOL PERSISTENCE TESTS PASSED")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
