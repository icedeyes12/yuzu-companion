"""Ollama provider implementation using BaseAIProvider.

Follows the new provider pattern with retry, circuit breaker, and normalization.
"""

from typing import List, Dict, Any, Optional, Generator

from ....domain.interfaces import AIProvider, ProviderCapabilities
from ....domain.interfaces.ai_provider import LLMRequest, LLMResponse
from ..base_provider import BaseAIProvider


class OllamaProvider(BaseAIProvider):
    """Ollama AI provider.
    
    Supports local and cloud-based Ollama instances.
    """
    
    DEFAULT_MODELS = [
        "smollm:360m",
        "smollm2:360m",
        "glm-4.6:cloud",
        "qwen3-vl:235b-cloud",
        "qwen3-coder:480b-cloud",
        "kimi-k2:1t-cloud",
        "kimi-k2.5:cloud",
        "gpt-oss:120b-cloud",
        "gpt-oss:20b-cloud",
        "deepseek-v3.1:671b-cloud"
    ]
    
    VISION_MODELS = [
        "qwen3-vl:235b-cloud",
        "kimi-k2.5:cloud"
    ]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._base_url = self._config.get("base_url", "http://127.0.0.1:11434")
    
    @property
    def name(self) -> str:
        return "ollama"
    
    @property
    def is_available(self) -> bool:
        return self.test_connection()
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=True,
            supports_vision=True,
            supports_image_generation=False,
            supports_system_prompt=True,
            max_context_length=8192,
        )
    
    def get_models(self) -> List[str]:
        return self.DEFAULT_MODELS
    
    def get_model_info(self, model: str) -> Dict[str, Any]:
        return {
            "name": model,
            "is_vision": model in self.VISION_MODELS,
            "supports_streaming": True,
        }
    
    def _do_send_message(
        self, messages: List[Dict[str, Any]], model: str
    ) -> Optional[str]:
        """Internal implementation - called by base class with retry."""
        if model not in self.DEFAULT_MODELS:
            return None
        
        try:
            import requests
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self._config.get("temperature", 0.69),
                    "top_p": self._config.get("top_p", 0.7),
                    "top_k": self._config.get("top_k", 40),
                    "typical_p": self._config.get("typical_p", 0.8),
                    "num_ctx": self._config.get("num_ctx", 8192),
                }
            }
            
            response = requests.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=self._config.get("timeout", 180),
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("message", {}).get("content", "").strip()
            else:
                return None
                
        except Exception as e:
            print(f"[OllamaProvider] Error: {e}")
            return None
    
    def _do_send_message_streaming(
        self, messages: List[Dict[str, Any]], model: str
    ) -> Generator[str, None, None]:
        """Internal streaming implementation."""
        if model not in self.DEFAULT_MODELS:
            yield ""
            return
        
        try:
            import requests
            import json
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": self._config.get("temperature", 0.69),
                    "top_p": self._config.get("top_p", 0.7),
                    "top_k": self._config.get("top_k", 40),
                    "typical_p": self._config.get("typical_p", 0.8),
                    "num_ctx": self._config.get("num_ctx", 8192),
                }
            }
            
            response = requests.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=self._config.get("timeout", 180),
                stream=True,
            )
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            json_data = json.loads(line.decode("utf-8"))
                            if "message" in json_data and "content" in json_data["message"]:
                                content = json_data["message"]["content"]
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
            else:
                yield ""
                
        except Exception as e:
            print(f"[OllamaProvider] Streaming error: {e}")
            yield f"Error: {str(e)}"
    
    def test_connection(self) -> bool:
        """Test Ollama connection."""
        try:
            import requests
            response = requests.get(
                f"{self._base_url}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
