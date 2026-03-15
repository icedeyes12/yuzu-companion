"""AI Provider interfaces (Ports).

Abstract contracts for LLM providers (Ollama, OpenRouter, Cerebras, Chutes).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncGenerator
from enum import Enum


class ProviderType(Enum):
    """Supported provider types."""
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    CEREBRAS = "cerebras"
    CHUTES = "chutes"


@dataclass
class LLMMessage:
    """Single message in LLM conversation."""
    role: str
    content: Any  # str or list[dict] for multimodal


@dataclass
class LLMRequest:
    """Request to LLM provider."""
    messages: List[LLMMessage]
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    top_k: int = 40
    stream: bool = False
    timeout: int = 180


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[Dict] = None


@dataclass
class ProviderCapabilities:
    """Capabilities of a provider/model."""
    supports_vision: bool = False
    supports_streaming: bool = True
    supports_tools: bool = False
    max_context_length: int = 8192
    supported_modalities: List[str] = field(default_factory=lambda: ["text"])


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and reachable."""
        pass

    @abstractmethod
    def get_models(self) -> List[str]:
        """Get list of available models."""
        pass

    @abstractmethod
    def get_capabilities(self, model: str) -> ProviderCapabilities:
        """Get capabilities for a specific model."""
        pass

    @abstractmethod
    async def send_message(self, request: LLMRequest) -> LLMResponse:
        """Send messages and get response (non-streaming)."""
        pass

    @abstractmethod
    async def send_message_streaming(
        self, request: LLMRequest
    ) -> AsyncGenerator[str, None]:
        """Send messages and stream response chunks."""
        pass

    @abstractmethod
    def supports_vision(self, model: str) -> bool:
        """Check if model supports vision."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if provider connection works."""
        pass

    @abstractmethod
    def normalize_messages(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Normalize messages for this provider (handle tool roles, etc)."""
        pass


class ProviderRegistry(ABC):
    """Registry for managing multiple AI providers."""

    @abstractmethod
    def register(self, provider: AIProvider) -> None:
        """Register a provider."""
        pass

    @abstractmethod
    def get(self, name: str) -> Optional[AIProvider]:
        """Get provider by name."""
        pass

    @abstractmethod
    def get_available(self) -> List[str]:
        """Get list of available provider names."""
        pass

    @abstractmethod
    def get_all_models(self) -> Dict[str, List[str]]:
        """Get all models from all providers."""
        pass

    @abstractmethod
    def get_preferred_provider(self) -> Optional[AIProvider]:
        """Get the user's preferred provider."""
        pass
