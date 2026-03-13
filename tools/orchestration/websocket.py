"""
WebSocket Handler for real-time tool updates

Provides:
- WebSocket connection management
- Tool progress streaming
- Message streaming
- Connection lifecycle handling
"""

import json
import uuid
import threading
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# Note: This is a pure Python implementation that can work with
# Flask-SocketIO or as a standalone. The actual integration depends
# on the web framework used.


class MessageType(Enum):
    """WebSocket message types"""
    # Client -> Server
    USER_MESSAGE = "message"
    TYPING_STATUS = "typing"
    PING = "ping"
    
    # Server -> Client
    TOOL_UPDATE = "tool_update"
    TOOL_COMPLETE = "tool_complete"
    ASSISTANT_CHUNK = "stream_chunk"
    ERROR = "error"
    PONG = "pong"


@dataclass
class WSMessage:
    """WebSocket message structure"""
    type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: __import__('time').time())


@dataclass
class ToolUpdate:
    """Real-time tool execution update"""
    execution_id: str
    tool_name: str
    status: str  # pending, running, success, error
    progress: Optional[int] = None  # 0-100
    status_text: Optional[str] = None


@dataclass
class ToolComplete:
    """Tool execution completed"""
    execution_id: str
    card_spec: Dict[str, Any]
    llm_prompt: Optional[str] = None


class WebSocketHandler:
    """
    Handles WebSocket connections and message routing.
    
    This class provides the core WebSocket logic that can be
    integrated with Flask-SocketIO or other frameworks.
    """
    
    def __init__(self):
        self._connections: Dict[str, Dict] = {}  # sid -> connection info
        self._lock = threading.Lock()
        self._handlers: Dict[str, List[Callable]] = {
            MessageType.USER_MESSAGE.value: [],
            MessageType.TYPING_STATUS.value: [],
            MessageType.PING.value: [],
        }
        self._broadcast_handlers: List[Callable] = []
    
    def connect(self, sid: str, session_id: str = None) -> bool:
        """
        Handle new WebSocket connection.
        
        Args:
            sid: Session ID (socket ID)
            session_id: Optional chat session ID
        
        Returns:
            True if connection accepted
        """
        with self._lock:
            self._connections[sid] = {
                "session_id": session_id,
                "connected_at": __import__('time').time(),
                "authenticated": True  # Could add auth check here
            }
            print(f"[WS] Client connected: {sid}")
            return True
    
    def disconnect(self, sid: str):
        """Handle WebSocket disconnection"""
        with self._lock:
            if sid in self._connections:
                del self._connections[sid]
                print(f"[WS] Client disconnected: {sid}")
    
    def send_to_client(self, sid: str, message: WSMessage):
        """
        Send message to a specific client.
        
        Override this method in integration to use actual WebSocket send.
        """
        # Default implementation - override in actual integration
        print(f"[WS] Would send to {sid}: {message.type}")
    
    def broadcast(self, message: WSMessage, session_id: str = None):
        """
        Broadcast message to all connected clients or those in a session.
        
        Override this method in integration to use actual WebSocket broadcast.
        """
        # Default implementation - override in actual integration
        with self._lock:
            sids = list(self._connections.keys())
        
        for sid in sids:
            if session_id is None or self._connections[sid].get("session_id") == session_id:
                self.send_to_client(sid, message)
    
    def handle_message(self, sid: str, raw_message: str):
        """
        Handle incoming WebSocket message.
        
        Args:
            sid: Client session ID
            raw_message: Raw message string
        """
        try:
            data = json.loads(raw_message)
            msg_type = data.get("type")
            payload = data.get("data", {})
            
            if msg_type == MessageType.USER_MESSAGE.value:
                self._handle_user_message(sid, payload)
            elif msg_type == MessageType.TYPING_STATUS.value:
                self._handle_typing_status(sid, payload)
            elif msg_type == MessageType.PING.value:
                self._handle_ping(sid)
            else:
                print(f"[WS] Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            print(f"[WS] Invalid JSON from {sid}: {raw_message}")
        except Exception as e:
            print(f"[WS] Error handling message: {e}")
    
    def _handle_user_message(self, sid: str, payload: Dict):
        """Handle user chat message"""
        # Call registered handlers
        for handler in self._handlers[MessageType.USER_MESSAGE.value]:
            try:
                handler(sid, payload)
            except Exception as e:
                print(f"[WS] Handler error: {e}")
    
    def _handle_typing_status(self, sid: str, payload: Dict):
        """Handle typing status update"""
        for handler in self._handlers[MessageType.TYPING_STATUS.value]:
            try:
                handler(sid, payload)
            except Exception as e:
                print(f"[WS] Handler error: {e}")
    
    def _handle_ping(self, sid: str):
        """Handle ping - respond with pong"""
        self.send_to_client(sid, WSMessage(
            type=MessageType.PONG.value,
            data={"timestamp": __import__('time').time()}
        ))
    
    def register_handler(self, msg_type: str, handler: Callable):
        """Register a handler for a message type"""
        if msg_type in self._handlers:
            self._handlers[msg_type].append(handler)
    
    # Tool update methods
    
    def emit_tool_update(self, session_id: str, update: ToolUpdate):
        """Send tool execution progress update"""
        message = WSMessage(
            type=MessageType.TOOL_UPDATE.value,
            data={
                "execution_id": update.execution_id,
                "tool_name": update.tool_name,
                "status": update.status,
                "progress": update.progress,
                "status_text": update.status_text
            }
        )
        self.broadcast(message, session_id=session_id)
    
    def emit_tool_complete(self, session_id: str, complete: ToolComplete):
        """Send tool execution completed"""
        message = WSMessage(
            type=MessageType.TOOL_COMPLETE.value,
            data={
                "execution_id": complete.execution_id,
                "card_spec": complete.card_spec,
                "llm_prompt": complete.llm_prompt
            }
        )
        self.broadcast(message, session_id=session_id)
    
    def emit_stream_chunk(self, sid: str, message_id: str, content: str, 
                          is_tool_commentary: bool = False):
        """Send assistant message chunk"""
        message = WSMessage(
            type=MessageType.ASSISTANT_CHUNK.value,
            data={
                "message_id": message_id,
                "content": content,
                "is_tool_commentary": is_tool_commentary
            }
        )
        self.send_to_client(sid, message)
    
    def emit_error(self, sid: str, code: str, error_message: str):
        """Send error to client"""
        message = WSMessage(
            type=MessageType.ERROR.value,
            data={
                "code": code,
                "message": error_message
            }
        )
        self.send_to_client(sid, message)
    
    # Connection info
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        with self._lock:
            return len(self._connections)
    
    def get_session_connections(self, session_id: str) -> List[str]:
        """Get all connection SIDs for a session"""
        with self._lock:
            return [
                sid for sid, info in self._connections.items()
                if info.get("session_id") == session_id
            ]


class WebSocketIntegration:
    """
    Integration layer for WebSocket frameworks.
    
    Use this to integrate WebSocketHandler with Flask-SocketIO.
    """
    
    def __init__(self, socketio=None):
        self.handler = WebSocketHandler()
        self.socketio = socketio
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup internal handlers"""
        # Override send_to_client to use SocketIO
        original_send = self.handler.send_to_client
        
        def socketio_send(sid: str, message: WSMessage):
            if self.socketio:
                self.socketio.emit(
                    message.type,
                    message.data,
                    room=sid
                )
        
        self.handler.send_to_client = socketio_send
    
    def on_connect(self, sid: str, environ: Dict):
        """Handle SocketIO connect event"""
        # Extract session from auth or query params
        session_id = environ.get("QUERY_STRING", {}).get("session_id")
        return self.handler.connect(sid, session_id)
    
    def on_disconnect(self, sid: str):
        """Handle SocketIO disconnect event"""
        self.handler.disconnect(sid)
    
    def on_message(self, sid: str, data: Any):
        """Handle SocketIO message event"""
        if isinstance(data, str):
            self.handler.handle_message(sid, data)
    
    def emit_tool_update(self, session_id: str, update: ToolUpdate):
        """Emit tool update to session room"""
        if self.socketio:
            self.socketio.emit(
                "tool_update",
                {
                    "execution_id": update.execution_id,
                    "tool_name": update.tool_name,
                    "status": update.status,
                    "progress": update.progress,
                    "status_text": update.status_text
                },
                room=session_id
            )


# Singleton instance
_ws_handler = None

def get_ws_handler() -> WebSocketHandler:
    """Get or create WebSocketHandler singleton"""
    global _ws_handler
    if _ws_handler is None:
        _ws_handler = WebSocketHandler()
    return _ws_handler
