"""CLI adapter - Bridge between old CLI and new domain services.

This module provides adapter methods that can be used to gradually
migrate main.py to the new architecture while keeping it functional.
"""

from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass

from ...infrastructure.config.container import get_container, FeatureFlags
from ...application.handlers.chat_handler import get_chat_handler, handle_user_message


@dataclass
class CLICommandResult:
    """Result from CLI command execution."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class CLIAdapter:
    """Adapter for CLI operations.
    
    Bridges old main.py CLIAgent to new domain services.
    Provides gradual migration path with feature flags.
    """
    
    def __init__(self):
        """Initialize adapter with services from container."""
        self._container = get_container()
        self._chat_handler = get_chat_handler()
    
    # ==================== Chat Operations ====================
    
    def send_message(
        self,
        user_message: str,
        interface: str = "terminal",
        streaming: bool = False
    ) -> str:
        """Send message and get response.
        
        Routes to new handler when USE_NEW_CHAT_HANDLER is enabled.
        """
        if FeatureFlags.USE_NEW_CHAT_HANDLER:
            if streaming:
                # For streaming, collect all chunks
                chunks = []
                for chunk in self._chat_handler.handle_message_streaming(
                    user_message, interface
                ):
                    chunks.append(chunk)
                return "".join(chunks)
            else:
                return self._chat_handler.handle_message(user_message, interface)
        else:
            # Legacy path - app.py functions
            if streaming:
                from app import handle_user_message_streaming
                chunks = list(handle_user_message_streaming(user_message, interface))
                return "".join(chunks)
            else:
                from app import handle_user_message
                return handle_user_message(user_message, interface)
    
    # ==================== Session Operations ====================
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """Get all chat sessions."""
        if FeatureFlags.USE_NEW_SESSION_REPO:
            repo = self._container.session_repository()
            return repo.get_all()
        else:
            from database import Database
            return Database.get_all_sessions()
    
    def get_active_session(self) -> Optional[Dict[str, Any]]:
        """Get currently active session."""
        if FeatureFlags.USE_NEW_SESSION_REPO:
            repo = self._container.session_repository()
            return repo.get_active()
        else:
            from database import Database
            return Database.get_active_session()
    
    def switch_session(self, session_id: int) -> bool:
        """Switch to different session."""
        if FeatureFlags.USE_NEW_SESSION_REPO:
            repo = self._container.session_repository()
            return repo.switch_to(session_id)
        else:
            from database import Database
            return Database.switch_session(session_id)
    
    def create_session(self, name: str) -> int:
        """Create new chat session."""
        if FeatureFlags.USE_NEW_SESSION_REPO:
            repo = self._container.session_repository()
            return repo.create(name)
        else:
            from database import Database
            return Database.create_session(name)
    
    def delete_session(self, session_id: int) -> bool:
        """Delete a session."""
        if FeatureFlags.USE_NEW_SESSION_REPO:
            repo = self._container.session_repository()
            return repo.delete(session_id)
        else:
            from database import Database
            return Database.delete_session(session_id)
    
    # ==================== Profile Operations ====================
    
    def get_profile(self) -> Dict[str, Any]:
        """Get user profile."""
        if FeatureFlags.USE_NEW_PROFILE_REPO:
            repo = self._container.profile_repository()
            return repo.get()
        else:
            from database import Database
            return Database.get_profile()
    
    def update_profile(self, updates: Dict[str, Any]) -> bool:
        """Update profile fields."""
        if FeatureFlags.USE_NEW_PROFILE_REPO:
            repo = self._container.profile_repository()
            profile = repo.get()
            if profile:
                # Update fields
                for key, value in updates.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                return repo.save(profile)
            return False
        else:
            from database import Database
            Database.update_profile(updates)
            return True
    
    # ==================== Provider Operations ====================
    
    def get_available_providers(self) -> List[str]:
        """Get list of available AI providers."""
        if FeatureFlags.USE_NEW_CHAT_HANDLER:
            from ...infrastructure.ai import get_provider_registry
            registry = get_provider_registry()
            return registry.get_available_providers()
        else:
            from app import get_available_providers
            return get_available_providers()
    
    def set_preferred_provider(self, provider: str, model: Optional[str] = None) -> str:
        """Set preferred AI provider and model."""
        if FeatureFlags.USE_NEW_PROFILE_REPO:
            repo = self._container.profile_repository()
            profile = repo.get()
            if profile:
                profile.preferences.preferred_provider = provider
                if model:
                    profile.preferences.preferred_model = model
                repo.save(profile)
                return f"Provider set to: {provider}"
        
        from app import set_preferred_provider
        return set_preferred_provider(provider, model)
    
    # ==================== Command Handlers ====================
    
    def handle_command(self, command: str, args: List[str]) -> CLICommandResult:
        """Handle CLI command.
        
        Returns structured result for CLI display.
        """
        cmd = command.lower()
        
        if cmd in ["exit", "quit", "bye"]:
            return CLICommandResult(True, "Goodbye!", {"action": "exit"})
        
        elif cmd == "help":
            return CLICommandResult(True, self._get_help_text())
        
        elif cmd == "model":
            if args:
                model = args[0]
                # Parse provider/model format
                if "/" in model:
                    provider, model_name = model.split("/", 1)
                    result = self.set_preferred_provider(provider, model_name)
                    return CLICommandResult(True, result)
                else:
                    profile = self.get_profile()
                    provider = profile.get("providers_config", {}).get("preferred_provider", "ollama")
                    result = self.set_preferred_provider(provider, model)
                    return CLICommandResult(True, result)
            else:
                providers = self.get_available_providers()
                return CLICommandResult(True, f"Available providers: {', '.join(providers)}")
        
        elif cmd == "session":
            sessions = self.list_sessions()
            return CLICommandResult(True, f"Sessions: {len(sessions)}", {"sessions": sessions})
        
        elif cmd == "stream":
            if args:
                enabled = args[0].lower() in ["on", "true", "1", "yes"]
                profile = self.get_profile()
                providers_config = profile.get("providers_config", {})
                providers_config["streaming_enabled"] = enabled
                self.update_profile({"providers_config": providers_config})
                status = "enabled" if enabled else "disabled"
                return CLICommandResult(True, f"Streaming {status}")
            else:
                profile = self.get_profile()
                enabled = profile.get("providers_config", {}).get("streaming_enabled", False)
                return CLICommandResult(True, f"Streaming: {'ON' if enabled else 'OFF'}")
        
        else:
            return CLICommandResult(False, f"Unknown command: {command}")
    
    def _get_help_text(self) -> str:
        """Generate help text."""
        return """
Available commands:
  /help              - Show this help
  /exit, /quit       - Exit the application
  /model [provider/model] - Set AI model
  /session           - List sessions
  /stream on|off     - Toggle streaming mode
  /imagine <prompt>  - Generate image
        """.strip()

    def get_status(self) -> Dict[str, Any]:
        """Get adapter status with container, feature flags, and chat handler info."""
        return {
            "container": self._container is not None,
            "feature_flags": {
                "USE_NEW_CHAT_HANDLER": FeatureFlags.USE_NEW_CHAT_HANDLER,
                "USE_NEW_DATABASE": FeatureFlags.USE_NEW_DATABASE,
            },
            "chat_handler": self._chat_handler is not None,
        }


# Singleton instance
_cli_adapter: Optional[CLIAdapter] = None


def get_cli_adapter() -> CLIAdapter:
    """Get or create CLI adapter singleton."""
    global _cli_adapter
    if _cli_adapter is None:
        _cli_adapter = CLIAdapter()
    return _cli_adapter
