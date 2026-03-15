"""User domain models."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class PartnerProfile:
    """Partner (AI companion) profile."""
    name: str
    relationship_stage: str = ""
    personality: str = ""


@dataclass
class UserPreferences:
    """User preferences and settings."""
    providers_config: Dict[str, Any] = field(default_factory=dict)
    image_model: str = "hunyuan"
    vision_model: str = "moonshotai/Kimi-K2.5-TEE"
    streaming_enabled: bool = False
    preferred_provider: str = "ollama"
    preferred_model: str = "glm-4.6:cloud"


@dataclass
class ApiKeys:
    """Container for API keys (by provider)."""
    keys: Dict[str, str] = field(default_factory=dict, repr=False)
    
    def get(self, provider: str) -> Optional[str]:
        """Get API key for provider."""
        return self.keys.get(provider)
    
    def set(self, provider: str, key: str) -> None:
        """Set API key for provider."""
        self.keys[provider] = key
    
    def has_key(self, provider: str) -> bool:
        """Check if key exists for provider."""
        return provider in self.keys and bool(self.keys[provider])


@dataclass
class Profile:
    """User profile aggregate root."""
    id: int
    display_name: str
    partner: PartnerProfile
    affection: int = 50
    theme: str = "default"
    preferences: UserPreferences = field(default_factory=UserPreferences)
    api_keys: ApiKeys = field(default_factory=ApiKeys)
    memory: Dict[str, Any] = field(default_factory=dict)
    global_knowledge: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update_affection(self, delta: int) -> int:
        """Update affection score and return new value."""
        self.affection = max(0, min(100, self.affection + delta))
        self.updated_at = datetime.now()
        return self.affection
    
    def get_preferred_provider(self) -> str:
        """Get preferred AI provider."""
        return self.preferences.preferred_provider
    
    def get_preferred_model(self) -> str:
        """Get preferred AI model."""
        return self.preferences.preferred_model
    
    def is_streaming_enabled(self) -> bool:
        """Check if streaming is enabled."""
        return self.preferences.streaming_enabled
