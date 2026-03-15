"""Base provider with retry, circuit breaker, and normalization.

This base class provides:
- Retry logic with exponential backoff
- Circuit breaker pattern for fault tolerance
- Message normalization (tool roles -> assistant)
- Vision support detection
"""

import time
import functools
from typing import Callable, Any, Optional, Generator
from dataclasses import dataclass
from enum import Enum

from ...domain.interfaces import AIProvider, LLMRequest, LLMResponse, ProviderCapabilities
from ...domain.models import Message, MessageRole


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject fast
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Simple circuit breaker implementation."""
    failure_threshold: int = 3
    recovery_timeout: float = 30.0
    _state: CircuitState = CircuitState.CLOSED
    _failure_count: int = 0
    _last_failure_time: Optional[float] = None
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self._state == CircuitState.OPEN:
            if time.time() - (self._last_failure_time or 0) > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise
    
    def _record_success(self):
        """Record successful call."""
        self._failure_count = 0
        self._state = CircuitState.CLOSED
    
    def _record_failure(self):
        """Record failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
    
    @property
    def state(self) -> CircuitState:
        return self._state


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 10.0):
    """Decorator for retry logic with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Don't retry on certain errors
                    if _is_non_retryable_error(e):
                        raise
                    
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        time.sleep(delay)
            
            # All retries exhausted
            if last_exception:
                raise last_exception
            
            return None
        
        return wrapper
    return decorator


def _is_non_retryable_error(error: Exception) -> bool:
    """Check if error should not trigger retry."""
    non_retryable = (
        "authentication",
        "unauthorized",
        "invalid api key",
        "quota exceeded",
        "rate limit",  # Some rate limits should be retried with backoff
    )
    error_str = str(error).lower()
    return any(term in error_str for term in non_retryable[:3])


class BaseAIProvider(AIProvider):
    """Base class for AI providers with common functionality."""
    
    def __init__(self, name: str, base_url: str):
        self._name = name
        self._base_url = base_url
        self._circuit_breaker = CircuitBreaker()
        self._capabilities = ProviderCapabilities()
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def is_available(self) -> bool:
        return self._circuit_breaker.state != CircuitState.OPEN
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities
    
    def send_message(self, request: LLMRequest) -> LLMResponse:
        """Send message with circuit breaker and retry."""
        try:
            # Normalize messages before sending
            normalized_messages = self._normalize_messages(request.messages)
            normalized_request = LLMRequest(
                messages=normalized_messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                top_k=request.top_k,
                stream=request.stream,
                timeout=request.timeout,
            )
            
            # Execute with circuit breaker
            result = self._circuit_breaker.call(
                self._send_message_impl,
                normalized_request
            )
            
            return result
            
        except CircuitOpenError:
            return LLMResponse(
                content="",
                error="Service temporarily unavailable (circuit open)",
                model=request.model,
                provider=self._name,
            )
        except Exception as e:
            return LLMResponse(
                content="",
                error=str(e),
                model=request.model,
                provider=self._name,
            )
    
    def send_message_streaming(self, request: LLMRequest) -> Generator[str, None, None]:
        """Send streaming message with normalization."""
        try:
            normalized_messages = self._normalize_messages(request.messages)
            normalized_request = LLMRequest(
                messages=normalized_messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                top_k=request.top_k,
                stream=True,
                timeout=request.timeout,
            )
            
            yield from self._send_message_streaming_impl(normalized_request)
            
        except CircuitOpenError:
            yield "[Service temporarily unavailable]"
        except Exception as e:
            yield f"[Error: {str(e)}]"
    
    def _normalize_messages(self, messages: list) -> list:
        """Normalize messages: convert custom tool roles to 'assistant'.
        
        This centralizes the normalization that was duplicated across providers.
        """
        standard_roles = {'system', 'user', 'assistant', 'tool'}
        normalized = []
        
        for msg in messages:
            role = msg.get('role', '')
            
            if role not in standard_roles:
                # Custom tool role - convert to assistant with marker
                content = msg.get('content', '')
                normalized_content = f"[{role}]\n{content}"
                normalized.append({
                    'role': 'assistant',
                    'content': normalized_content
                })
            else:
                normalized.append(msg)
        
        return normalized
    
    def supports_vision(self, model: str) -> bool:
        """Check if model supports vision."""
        vision_keywords = ['vision', 'vl', 'kimi', 'gpt-4', 'claude']
        return any(kw in model.lower() for kw in vision_keywords)
    
    def format_vision_message(self, text: str, image_urls: list) -> list:
        """Format vision message for multimodal input."""
        content = [{"type": "text", "text": text}]
        
        for url in image_urls[:3]:  # Limit to 3 images
            content.append({
                "type": "image_url",
                "image_url": {"url": url}
            })
        
        return [{"role": "user", "content": content}]
    
    def test_connection(self) -> bool:
        """Test provider connection."""
        try:
            models = self.get_models()
            return len(models) > 0
        except:
            return False
    
    # Abstract methods that subclasses must implement
    
    def get_models(self) -> list:
        """Get available models. Must be implemented by subclass."""
        raise NotImplementedError
    
    def _send_message_impl(self, request: LLMRequest) -> LLMResponse:
        """Internal implementation. Must be implemented by subclass."""
        raise NotImplementedError
    
    def _send_message_streaming_impl(self, request: LLMRequest) -> Generator[str, None, None]:
        """Internal streaming implementation. Must be implemented by subclass."""
        raise NotImplementedError
