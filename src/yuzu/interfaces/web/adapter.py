"""Web adapter - Bridge between old Flask web.py and new domain services."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import json

from ...infrastructure.config.container import get_container, FeatureFlags
from ...application.handlers.chat_handler import (
    get_chat_handler,
    handle_user_message,
    handle_user_message_streaming
)


@dataclass
class WebResponse:
    """Standard web API response."""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"status": self.status, "message": self.message}
        if self.data:
            result.update(self.data)
        return result


class WebAdapter:
    """Adapter for Flask web operations."""
    
    def __init__(self):
        self._container = get_container()
        self._chat_handler = get_chat_handler()
    
    def get_profile(self) -> WebResponse:
        """Get user profile and session info."""
        try:
            from database import Database
            profile = Database.get_profile()
            active_session = Database.get_active_session()
            chat_history = Database.get_chat_history()
            
            return WebResponse(
                status="success",
                message="Profile loaded",
                data={
                    **profile,
                    "chat_history": chat_history,
                    "active_session": active_session,
                }
            )
        except Exception as e:
            return WebResponse(
                status="error",
                message=f"Failed to load profile: {str(e)}"
            )
    
    def send_message(self, message: str) -> WebResponse:
        """Send message and get response."""
        if not message or not message.strip():
            return WebResponse(status="error", message="Please type a message!")
        
        try:
            response = handle_user_message(message, interface="web")
            return WebResponse(
                status="success",
                message="Message processed",
                data={"reply": response}
            )
        except Exception as e:
            return WebResponse(status="error", message="Sorry, I encountered an error.")
    
    def send_message_streaming(self, message: str):
        """Send message and stream response."""
        if not message or not message.strip():
            yield 'data: {"chunk": "Please type a message!"}\n\n'
            return
        
        try:
            import json
            for chunk in handle_user_message_streaming(message, interface="web"):
                if chunk:
                    yield f'data: {{"chunk": {json.dumps(chunk)}}}\n\n'
        except Exception as e:
            yield f'data: {{"chunk": "Sorry, I encountered an error."}}\n\n'


# Singleton
_web_adapter: Optional[WebAdapter] = None

def get_web_adapter() -> WebAdapter:
    global _web_adapter
    if _web_adapter is None:
        _web_adapter = WebAdapter()
    return _web_adapter
