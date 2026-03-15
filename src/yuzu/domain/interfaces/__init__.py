"""Domain interfaces (Ports) - Abstract contracts for infrastructure implementations.

These interfaces define the contracts that the infrastructure layer must implement.
The domain layer depends only on these abstractions, not concrete implementations.
"""

from .db_interface import (
    ProfileRepository,
    SessionRepository,
    MessageRepository,
    APIKeyRepository,
    UnitOfWork,
    Profile,
    ChatSession,
    Message,
    APIKey,
)
from .ai_provider import (
    AIProvider,
    ProviderRegistry,
    LLMRequest,
    LLMResponse,
    LLMMessage,
    ProviderCapabilities,
    ProviderType,
)
from .tool_interface import (
    ToolExecutor,
    ToolRegistry,
    ToolOrchestrator,
    ToolResult as ToolInterfaceResult,
    ToolContext,
    ToolType,
    ToolStatus,
)
from .encryption_interface import Encryptor, EncryptionInfo

__all__ = [
    # Database
    "ProfileRepository",
    "SessionRepository",
    "MessageRepository",
    "APIKeyRepository",
    "UnitOfWork",
    "Profile",
    "ChatSession",
    "Message",
    "APIKey",
    # AI
    "AIProvider",
    "ProviderRegistry",
    "LLMRequest",
    "LLMResponse",
    "LLMMessage",
    "ProviderCapabilities",
    "ProviderType",
    # Tools
    "ToolExecutor",
    "ToolRegistry",
    "ToolOrchestrator",
    "ToolInterfaceResult",
    "ToolContext",
    "ToolType",
    "ToolStatus",
    # Security
    "Encryptor",
    "EncryptionInfo",
]
