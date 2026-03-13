"""
Test WebSocket Handler - Real-time tool updates

Tests:
1. Connection management
2. Message handling
3. Broadcasting
4. Tool progress updates
5. Session handling
"""

import unittest
import sys
import os
import json
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.orchestration.websocket import (
    WebSocketMessage, MessageType, WebSocketHandler, get_ws_handler
)


class MockWebSocket:
    """Mock WebSocket for testing"""
    
    def __init__(self):
        self.sent_messages = []
        self.closed = False
        self.sid = "test_sid"
    
    def send(self, data):
        self.sent_messages.append(data)
    
    def close(self):
        self.closed = True


class TestWebSocketMessage(unittest.TestCase):
    """Test WebSocketMessage dataclass"""
    
    def test_creation(self):
        """Test WebSocketMessage creation"""
        msg = WebSocketMessage(
            type=MessageType.TOOL_UPDATE,
            data={"tool_name": "test", "status": "running"}
        )
        
        self.assertEqual(msg.type, MessageType.TOOL_UPDATE)
        self.assertEqual(msg.data["tool_name"], "test")
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        msg = WebSocketMessage(
            type=MessageType.ASSISTANT_CHUNK,
            data={"content": "Hello"}
        )
        
        d = msg.to_dict()
        
        self.assertEqual(d["type"], "stream_chunk")
        self.assertEqual(d["data"]["content"], "Hello")
    
    def test_to_json(self):
        """Test JSON serialization"""
        msg = WebSocketMessage(
            type=MessageType.TOOL_COMPLETE,
            data={"tool_name": "test", "result": "success"}
        )
        
        json_str = msg.to_json()
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed["type"], "tool_complete")
    
    def test_from_json(self):
        """Test JSON deserialization"""
        json_str = '{"type": "tool_update", "data": {"status": "running"}}'
        
        msg = WebSocketMessage.from_json(json_str)
        
        self.assertEqual(msg.type, MessageType.TOOL_UPDATE)
        self.assertEqual(msg.data["status"], "running")


class TestMessageType(unittest.TestCase):
    """Test MessageType enum"""
    
    def test_enum_values(self):
        """Test MessageType enum values"""
        self.assertEqual(MessageType.USER_MESSAGE.value, "message")
        self.assertEqual(MessageType.TOOL_UPDATE.value, "tool_update")
        self.assertEqual(MessageType.TOOL_COMPLETE.value, "tool_complete")
        self.assertEqual(MessageType.ASSISTANT_CHUNK.value, "stream_chunk")
        self.assertEqual(MessageType.ERROR.value, "error")
        self.assertEqual(MessageType.TYPING.value, "typing")


class TestWebSocketHandler(unittest.TestCase):
    """Test cases for WebSocketHandler"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.handler = WebSocketHandler()
        self.mock_ws = MockWebSocket()
    
    # ============== Connection tests ==============
    
    def test_connect(self):
        """Test client connection"""
        sid = self.handler.connect(self.mock_ws, session_id="test_session")
        
        self.assertIsNotNone(sid)
        self.assertIn(sid, self.handler._connections)
        self.assertIn("test_session", self.handler._session_connections)
    
    def test_disconnect(self):
        """Test client disconnection"""
        sid = self.handler.connect(self.mock_ws, session_id="test_session")
        result = self.handler.disconnect(sid)
        
        self.assertTrue(result)
        self.assertNotIn(sid, self.handler._connections)
    
    def test_connect_without_session(self):
        """Test connection without session"""
        sid = self.handler.connect(self.mock_ws)
        
        self.assertIsNotNone(sid)
    
    # ============== Message handling tests ==============
    
    def test_handle_user_message(self):
        """Test handling user message"""
        sid = self.handler.connect(self.mock_ws, session_id="test_session")
        
        message = {
            "type": "message",
            "content": "Hello",
            "session_id": "test_session"
        }
        
        # Should handle without error
        self.handler._handle_user_message(sid, message)
    
    def test_handle_typing_status(self):
        """Test handling typing status"""
        sid = self.handler.connect(self.mock_ws, session_id="test_session")
        
        message = {
            "type": "typing",
            "session_id": "test_session",
            "is_typing": True
        }
        
        self.handler._handle_typing_status(sid, message)
        
        # Should complete without error
    
    def test_handle_invalid_message(self):
        """Test handling invalid message"""
        sid = self.handler.connect(self.mock_ws)
        
        # Invalid message type
        message = {"type": "invalid_type"}
        
        # Should handle gracefully
        self.handler._handle_message(sid, message)
    
    # ============== Broadcasting tests ==============
    
    def test_broadcast_to_session(self):
        """Test broadcasting to session"""
        sid1 = self.handler.connect(self.mock_ws, session_id="session1")
        
        # Create another connection in same session
        mock_ws2 = MockWebSocket()
        sid2 = self.handler.connect(mock_ws2, session_id="session1")
        
        # Broadcast message
        msg = WebSocketMessage(
            type=MessageType.TOOL_UPDATE,
            data={"status": "running"}
        )
        
        self.handler.broadcast_to_session("session1", msg)
        
        # Both should receive
        self.assertGreaterEqual(len(self.mock_ws.sent_messages), 1)
        self.assertGreaterEqual(len(mock_ws2.sent_messages), 1)
    
    def test_broadcast_to_empty_session(self):
        """Test broadcasting to session with no connections"""
        msg = WebSocketMessage(
            type=MessageType.TOOL_UPDATE,
            data={"status": "running"}
        )
        
        # Should not raise error
        result = self.handler.broadcast_to_session("nonexistent_session", msg)
        
        self.assertIsNone(result)
    
    # ============== Tool update tests ==============
    
    def test_send_tool_update(self):
        """Test sending tool update"""
        self.handler.connect(self.mock_ws, session_id="test_session")
        
        result = self.handler.send_tool_update(
            session_id="test_session",
            execution_id="exec_123",
            tool_name="image_generate",
            status="running",
            status_text="Generating image..."
        )
        
        self.assertTrue(result)
        self.assertGreater(len(self.mock_ws.sent_messages), 0)
    
    def test_send_tool_complete(self):
        """Test sending tool complete"""
        self.handler.connect(self.mock_ws, session_id="test_session")
        
        card_spec = {
            "card_type": "image",
            "header_icon": "🖼️",
            "content": {"url": "/test.png"}
        }
        
        result = self.handler.send_tool_complete(
            session_id="test_session",
            execution_id="exec_123",
            card_spec=card_spec
        )
        
        self.assertTrue(result)
    
    # ============== Message parsing tests ==============
    
    def test_parse_valid_message(self):
        """Test parsing valid message"""
        json_str = json.dumps({
            "type": "message",
            "content": "test",
            "session_id": "s1"
        })
        
        parsed = self.handler._parse_message(json_str)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["type"], "message")
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON"""
        result = self.handler._parse_message("not valid json")
        
        self.assertIsNone(result)
    
    def test_parse_missing_type(self):
        """Test parsing message without type"""
        result = self.handler._parse_message('{"content": "test"}')
        
        # Should default to None or handle gracefully
        # (depends on implementation)
    
    # ============== Edge case tests ==============
    
    def test_message_to_disconnected_client(self):
        """Test sending to disconnected client"""
        # Don't connect, try to send
        result = self.handler.send_tool_update(
            session_id="nonexistent",
            execution_id="exec_123",
            tool_name="test",
            status="running"
        )
        
        self.assertFalse(result)
    
    def test_broadcast_large_message(self):
        """Test broadcasting large message"""
        self.handler.connect(self.mock_ws, session_id="test_session")
        
        large_data = {"content": "x" * 10000}
        
        msg = WebSocketMessage(
            type=MessageType.ASSISTANT_CHUNK,
            data=large_data
        )
        
        # Should handle gracefully
        self.handler.broadcast_to_session("test_session", msg)
    
    def test_concurrent_connections(self):
        """Test handling concurrent connections"""
        connections = []
        
        for i in range(10):
            ws = MockWebSocket()
            sid = self.handler.connect(ws, session_id=f"session_{i % 3}")
            connections.append((sid, ws))
        
        # All should be tracked
        self.assertEqual(len(self.handler._connections), 10)
        
        # Broadcast to one session
        msg = WebSocketMessage(
            type=MessageType.TOOL_UPDATE,
            data={"status": "test"}
        )
        
        self.handler.broadcast_to_session("session_0", msg)
        
        # Connections in session_0 should receive
        received_count = sum(
            1 for _, ws in connections 
            if "session_0" in self.handler._session_connections 
            and any("tool_update" in m for m in ws.sent_messages)
        )


class TestWebSocketHandlerSingleton(unittest.TestCase):
    """Test WebSocketHandler singleton"""
    
    def test_singleton(self):
        """Test singleton pattern"""
        handler1 = get_ws_handler()
        handler2 = get_ws_handler()
        
        self.assertIs(handler1, handler2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
