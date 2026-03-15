"""Chat application handler - New implementation of handle_user_message.

This is the main entry point for chat processing. It bridges the old interface
to the new domain services using the adapter pattern.
"""

from typing import Optional, Generator, Dict, Any, Callable
from dataclasses import dataclass

from ...domain.services import ChatService, ChatRequest, ChatResponse
from ...domain.services.tool_service import ToolService
from ...infrastructure.config.container import get_container, FeatureFlags


@dataclass
class HandlerResult:
    """Result from chat handler."""
    response: str
    tool_executed: bool = False
    tool_name: Optional[str] = None
    error: Optional[str] = None


class ChatHandler:
    """Application handler for chat requests.
    
    Bridges the old interface (user_message string) to the new
    domain services (ChatService, ToolService).
    """
    
    def __init__(
        self,
        chat_service: Optional[ChatService] = None,
        tool_service: Optional[ToolService] = None
    ):
        """Initialize with services (or get from container)."""
        container = get_container()
        
        # Initialize tool service first (needed by chat service)
        self._tool_service = tool_service or ToolService(
            container.message_repository
        )
        
        self._chat_service = chat_service or ChatService(
            profile_repo=container.profile_repository,
            session_repo=container.session_repository,
            message_repo=container.message_repository,
            provider_registry=container.provider_registry,
            tool_service=self._tool_service,
        )
    
    def handle_message(
        self,
        user_message: str,
        interface: str = "terminal",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        session_id: Optional[int] = None
    ) -> str:
        """Handle user message (non-streaming).
        
        This is the new implementation that routes to ChatService.
        Compatible with old app.py handle_user_message signature.
        """
        if FeatureFlags.USE_NEW_CHAT_HANDLER:
            return self._handle_new(user_message, interface, provider, model, session_id)
        else:
            # Fallback to legacy implementation
            return self._handle_legacy(user_message, interface, provider, model, session_id)
    
    def handle_message_streaming(
        self,
        user_message: str,
        interface: str = "terminal",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        session_id: Optional[int] = None
    ) -> Generator[str, None, None]:
        """Handle user message (streaming).
        
        Yields response chunks for real-time display.
        """
        if FeatureFlags.USE_NEW_CHAT_HANDLER:
            yield from self._handle_streaming_new(
                user_message, interface, provider, model, session_id
            )
        else:
            yield from self._handle_streaming_legacy(
                user_message, interface, provider, model, session_id
            )
    
    def _handle_new(
        self,
        user_message: str,
        interface: str,
        provider: Optional[str],
        model: Optional[str],
        session_id: Optional[int]
    ) -> str:
        """New implementation using ChatService."""
        try:
            # Detect tool intent before sending to AI
            intent = self._tool_service.detect_intent(user_message)
            
            if intent and intent.get("needs_tool"):
                # Tool detected - execute two-pass cycle
                result = self._chat_service.execute_tool_cycle(
                    session_id=session_id,
                    tool_name=intent["tool_name"],
                    tool_params=intent["params"],
                    user_message=user_message,
                    preferred_provider=provider,
                    preferred_model=model
                )
                return result.content
            
            # No tool - regular chat request
            request = ChatRequest(
                session_id=session_id,
                user_message=user_message,
                preferred_provider=provider,
                preferred_model=model
            )
            
            response = self._chat_service.execute_chat_request(request)
            return response.content
            
        except Exception as e:
            print(f"[ChatHandler] Error: {e}")
            import traceback
            traceback.print_exc()
            return f"I encountered an error: {str(e)}"
    
    def _handle_streaming_new(
        self,
        user_message: str,
        interface: str,
        provider: Optional[str],
        model: Optional[str],
        session_id: Optional[int]
    ) -> Generator[str, None, None]:
        """New streaming implementation."""
        # For now, collect and yield (full streaming support requires async refactor)
        response = self._handle_new(
            user_message, interface, provider, model, session_id
        )
        # Yield word by word for streaming effect
        words = response.split()
        for word in words:
            yield word + " "
    
    def _handle_legacy(
        self,
        user_message: str,
        interface: str,
        provider: Optional[str],
        model: Optional[str],
        session_id: Optional[int]
    ) -> str:
        """Fallback to legacy app.py implementation."""
        # Import here to avoid circular dependencies
        import sys
        sys.path.insert(0, "/home/workspace/yuzu-companion")
        from app import handle_user_message as legacy_handle
        
        return legacy_handle(user_message, interface)
    
    def _handle_streaming_legacy(
        self,
        user_message: str,
        interface: str,
        provider: Optional[str],
        model: Optional[str],
        session_id: Optional[int]
    ) -> Generator[str, None, None]:
        """Fallback to legacy streaming implementation."""
        import sys
        sys.path.insert(0, "/home/workspace/yuzu-companion")
        from app import handle_user_message_streaming as legacy_stream
        
        yield from legacy_stream(user_message, interface)


# Singleton instance for convenience
_handler_instance: Optional[ChatHandler] = None


def get_chat_handler() -> ChatHandler:
    """Get or create singleton chat handler."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = ChatHandler()
    return _handler_instance


def handle_user_message(
    user_message: str,
    interface: str = "terminal"
) -> str:
    """Drop-in replacement for app.py handle_user_message.
    
    Routes to new ChatHandler when feature flag is enabled.
    """
    handler = get_chat_handler()
    return handler.handle_message(user_message, interface)


def handle_user_message_streaming(
    user_message: str,
    interface: str = "terminal"
) -> Generator[str, None, None]:
    """Drop-in replacement for app.py handle_user_message_streaming."""
    handler = get_chat_handler()
    yield from handler.handle_message_streaming(user_message, interface)
