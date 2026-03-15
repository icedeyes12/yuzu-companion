"""Chat domain service - Core chat orchestration logic.

This service encapsulates the business logic previously in app.py:
- Building system prompts
- Managing conversation context
- Handling tool orchestration
- Managing streaming vs non-streaming responses
"""

from typing import Optional, List, Dict, Any, Generator, Tuple
from dataclasses import dataclass
from datetime import datetime

from ...domain.interfaces import (
    SessionRepository,
    MessageRepository,
    AIProvider,
    ProviderRegistry,
    ProfileRepository,
)
from ...domain.models import Profile, ChatSession, Message, MessageRole
from ...domain.services.tool_service import ToolService, ToolExecution


@dataclass
class ChatRequest:
    """Request to process a user message."""
    user_message: str
    session_id: Optional[int] = None
    provider_name: Optional[str] = None
    model_name: Optional[str] = None
    streaming: bool = False
    interface: str = "terminal"


@dataclass
class ChatResponse:
    """Response from processing a user message."""
    content: str
    is_tool_result: bool = False
    tool_name: Optional[str] = None
    streaming: bool = False
    stream_generator: Optional[Generator[str, None, None]] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ChatService:
    """Core chat domain service.
    
    Responsibilities:
    - Build LLM context (system + history)
    - Route to AI providers
    - Handle tool execution
    - Manage streaming responses
    - Store conversation history
    """
    
    # Tool roles that skip second pass
    TERMINAL_TOOL_ROLES = set()  # Empty: all tools get second pass now
    
    # Visual context TTL
    VISUAL_CONTEXT_TURNS = 3
    
    def __init__(
        self,
        profile_repo: ProfileRepository,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        provider_registry: ProviderRegistry,
        tool_service: ToolService,
    ):
        self._profile_repo = profile_repo
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._providers = provider_registry
        self._tool_service = tool_service
        
        # Session-level visual context cache
        self._visual_context: Dict[int, Dict[str, Any]] = {}
    
    def process_message(self, request: ChatRequest) -> ChatResponse:
        """Process a user message (non-streaming)."""
        # Get or create session
        session = self._get_session(request.session_id)
        profile = self._profile_repo.get()
        
        # Check for direct tool commands (/imagine, etc.)
        if self._is_direct_tool_command(request.user_message):
            return self._handle_direct_tool(request, session, profile)
        
        # Build context and get AI response
        messages = self._build_context(profile, session)
        
        # Add user message
        user_msg = Message(
            id=0,
            session_id=session.id,
            role=MessageRole.USER,
            content=request.user_message,
        )
        messages.append(user_msg.to_llm_format())
        
        # Store user message
        self._message_repo.add(user_msg)
        session.increment_message_count()
        
        # Get provider
        provider = self._get_provider(request.provider_name, profile)
        model = self._get_model(request.model_name, profile)
        
        # Call AI
        response_text = provider.send_message(messages, model)
        
        # Handle tool commands in response
        if self._is_tool_command(response_text):
            return self._handle_tool_response(
                response_text, session, profile, request.user_message
            )
        
        # Store assistant response
        assistant_msg = Message(
            id=0,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=response_text,
        )
        self._message_repo.add(assistant_msg)
        
        return ChatResponse(content=response_text)
    
    def process_message_streaming(
        self, request: ChatRequest
    ) -> Generator[str, None, None]:
        """Process a user message (streaming)."""
        session = self._get_session(request.session_id)
        profile = self._profile_repo.get()
        
        # Store user message
        user_msg = Message(
            id=0,
            session_id=session.id,
            role=MessageRole.USER,
            content=request.user_message,
        )
        self._message_repo.add(user_msg)
        session.increment_message_count()
        
        # Build context
        messages = self._build_context(profile, session)
        messages.append({
            "role": "user",
            "content": request.user_message,
        })
        
        # Get provider
        provider = self._get_provider(request.provider_name, profile)
        model = self._get_model(request.model_name, profile)
        
        # Collect streaming response
        full_response = []
        for chunk in provider.send_message_streaming(messages, model):
            yield chunk
            full_response.append(chunk)
        
        # Store complete response
        assistant_msg = Message(
            id=0,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content="".join(full_response),
        )
        self._message_repo.add(assistant_msg)
    
    def _get_session(self, session_id: Optional[int]) -> ChatSession:
        """Get session by ID or active session."""
        if session_id:
            session = self._session_repo.get_by_id(session_id)
            if session:
                return session
        
        session = self._session_repo.get_active()
        if session:
            return session
        
        # Create new session
        session_id = self._session_repo.create("New Chat")
        return self._session_repo.get_by_id(session_id)
    
    def _get_provider(self, name: Optional[str], profile: Profile) -> AIProvider:
        """Get AI provider."""
        if name:
            provider = self._providers.get_provider(name)
            if provider:
                return provider
        
        # Use preferred from profile
        preferred = profile.get_preferred_provider()
        provider = self._providers.get_provider(preferred)
        if provider:
            return provider
        
        # Fallback to first available
        available = self._providers.get_available_providers()
        if available:
            return self._providers.get_provider(available[0])
        
        raise RuntimeError("No AI provider available")
    
    def _get_model(self, name: Optional[str], profile: Profile) -> str:
        """Get model name."""
        if name:
            return name
        return profile.get_preferred_model()
    
    def _build_context(
        self, profile: Profile, session: ChatSession
    ) -> List[Dict[str, Any]]:
        """Build LLM context: system + history."""
        # Build system message
        system_content = self._build_system_message(profile, session)
        messages = [{"role": "system", "content": system_content}]
        
        # Add conversation history
        history = self._message_repo.get_history_for_ai(session.id, limit=25)
        for msg in history:
            messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })
        
        return messages
    
    def _build_system_message(
        self, profile: Profile, session: ChatSession
    ) -> str:
        """Build system message with profile and session context."""
        parts = []
        
        # Partner persona
        partner = profile.partner
        parts.append(f"You are {partner.name}, a companion AI.")
        
        if partner.personality:
            parts.append(f"Your personality: {partner.personality}")
        
        # Session context
        if session.memory.context:
            parts.append(f"\nSession context:\n{session.memory.context}")
        
        # Available tools
        parts.append("\nAvailable tools:")
        tools = self._tool_service.get_available_tools()
        for tool in tools:
            parts.append(f"- /{tool.name}: {tool.description}")
        parts.append("\nWhen you need to use a tool, respond ONLY with the command line.")
        
        return "\n".join(parts)
    
    def _is_direct_tool_command(self, message: str) -> bool:
        """Check if message is a direct tool command (/tool)."""
        return message.strip().startswith("/")
    
    def _is_tool_command(self, message: str) -> bool:
        """Check if response is a tool command."""
        if not message:
            return False
        lines = message.strip().split("\n")
        if not lines:
            return False
        return lines[0].strip().startswith("/")
    
    def _handle_direct_tool(
        self, request: ChatRequest, session: ChatSession, profile: Profile
    ) -> ChatResponse:
        """Handle direct tool command from user."""
        # Parse command
        parts = request.user_message.strip().split(None, 1)
        tool_name = parts[0][1:]  # Remove leading /
        args = parts[1] if len(parts) > 1 else ""
        
        # Execute tool
        result = self._tool_service.execute(
            tool_name=tool_name,
            args=args,
            session_id=session.id,
        )
        
        # Store tool result
        if result.is_success:
            tool_msg = self._message_repo.add_tool_result(
                session_id=session.id,
                tool_name=tool_name,
                result_content=result.formatted_output,
            )
        
        return ChatResponse(
            content=result.formatted_output,
            is_tool_result=True,
            tool_name=tool_name,
        )
    
    def _handle_tool_response(
        self,
        response_text: str,
        session: ChatSession,
        profile: Profile,
        original_message: str,
    ) -> ChatResponse:
        """Handle tool command from AI response."""
        # Parse command
        lines = response_text.strip().split("\n")
        first_line = lines[0].strip()
        
        parts = first_line.split(None, 1)
        tool_name = parts[0][1:]
        args = parts[1] if len(parts) > 1 else ""
        
        # Store AI's tool request
        tool_req_msg = Message(
            id=0,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=response_text,
        )
        self._message_repo.add(tool_req_msg)
        
        # Execute tool
        result = self._tool_service.execute(
            tool_name=tool_name,
            args=args,
            session_id=session.id,
        )
        
        # Store tool result
        self._message_repo.add_tool_result(
            session_id=session.id,
            tool_name=tool_name,
            result_content=result.formatted_output,
        )
        
        # Second pass: Get AI commentary on tool result
        # Build context including tool result
        messages = self._build_context(profile, session)
        messages.append({"role": "user", "content": original_message})
        messages.append({
            "role": "assistant",
            "content": f"[{tool_name}_tools]\n{result.formatted_output}",
        })
        
        # Get provider
        provider = self._get_provider(None, profile)
        model = self._get_model(None, profile)
        
        # Get AI commentary
        commentary = provider.send_message(messages, model)
        
        # Store commentary
        commentary_msg = Message(
            id=0,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=commentary,
        )
        self._message_repo.add(commentary_msg)
        
        # Return both tool result and commentary
        full_response = f"{result.formatted_output}\n\n{commentary}"
        
        return ChatResponse(
            content=full_response,
            is_tool_result=True,
            tool_name=tool_name,
        )
