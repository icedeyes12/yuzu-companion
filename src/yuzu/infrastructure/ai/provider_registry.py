"""Provider registry implementation.

Manages all AI providers and provider selection.
"""

from typing import List, Dict, Optional, Any

from ...domain.interfaces import ProviderRegistry, AIProvider


class AIProviderRegistry(ProviderRegistry):
    """Registry of AI providers.
    
    Manages provider lifecycle and selection.
    """
    
    def __init__(self):
        self._providers: Dict[str, AIProvider] = {}
    
    def register(self, provider: AIProvider) -> None:
        """Register a provider."""
        self._providers[provider.name] = provider
    
    def unregister(self, name: str) -> None:
        """Unregister a provider."""
        if name in self._providers:
            del self._providers[name]
    
    def get_provider(self, name: str) -> Optional[AIProvider]:
        """Get provider by name."""
        return self._providers.get(name)
    
    def get_available_providers(self) -> List[str]:
        """Get list of available (connected) providers."""
        return [
            name for name, provider in self._providers.items()
            if provider.is_available
        ]
    
    def get_all_models(self) -> Dict[str, List[str]]:
        """Get all models from all providers."""
        return {
            name: provider.get_models()
            for name, provider in self._providers.items()
        }
    
    def get_preferred_provider(
        self,
        preference: Optional[str] = None
    ) -> Optional[AIProvider]:
        """Get preferred provider or first available."""
        if preference and preference in self._providers:
            provider = self._providers[preference]
            if provider.is_available:
                return provider
        
        # Return first available
        for name in self.get_available_providers():
            return self._providers[name]
        
        return None
    
    def initialize_providers(self, config: Dict[str, Any]) -> None:
        """Initialize all providers from config."""
        # Import providers to avoid circular imports
        from .providers.ollama import OllamaProvider
        
        # Try Ollama
        ollama_config = config.get("ollama", {})
        ollama = OllamaProvider(ollama_config)
        if ollama.is_available:
            self.register(ollama)
            print(f"[ProviderRegistry] Registered: ollama")
        else:
            print(f"[ProviderRegistry] Ollama not available")
        
        # Other providers (will be added as they're refactored)
        # - OpenRouterProvider
        # - CerebrasProvider
        # - ChutesProvider
    
    def list_providers(self) -> List[Dict[str, Any]]:
        """List all providers with status."""
        return [
            {
                "name": name,
                "available": provider.is_available,
                "models": provider.get_models(),
            }
            for name, provider in self._providers.items()
        ]


# Singleton instance
_registry_instance: Optional[AIProviderRegistry] = None


def get_provider_registry() -> AIProviderRegistry:
    """Get global provider registry."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AIProviderRegistry()
    return _registry_instance
