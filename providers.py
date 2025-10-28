# [FILE: providers.py]
# [VERSION: 1.0.0.69.1]
# [DATE: 2025-08-12]
# [PROJECT: HKKM - Yuzu Companion]
# [DESCRIPTION: AI provider management with vision support]
# [AUTHOR: Project Lead: Bani Baskara]
# [TEAM: Deepseek, GPT, Qwen, Aihara]
# [REPOSITORY: https://guthib.com/icedeyes12]
# [LICENSE: MIT]

import requests
import json
import time
import os
from typing import List, Dict, Optional, Any
from database import Database
from tools import multimodal_tools

class AIProvider:
    def __init__(self, name: str, config: Dict = None):
        self.name = name
        self.config = config or {}
        self.is_available = True
    
    def get_models(self) -> List[str]:
        raise NotImplementedError
    
    def send_message(self, messages: List[Dict], model: str, **kwargs) -> Optional[str]:
        raise NotImplementedError
    
    def test_connection(self) -> bool:
        try:
            models = self.get_models()
            return len(models) > 0
        except:
            return False
    
    def supports_vision(self, model: str) -> bool:
        return multimodal_tools.is_vision_model(model, self.name)
    
    def format_vision_message(self, user_message: str) -> List[Dict]:
        return multimodal_tools.format_vision_message(user_message, self.name)

class OllamaProvider(AIProvider):
    def __init__(self, config: Dict = None):
        super().__init__("ollama", config)
        self.base_url = self.config.get('base_url', "http://127.0.0.1:11434")
        self.available_models = [
            "glm-4.6:cloud",
            "qwen3-vl:235b-cloud",
            "qwen3-coder:480b-cloud",
            "kimi-k2:1t-cloud",
            "gpt-oss:120b-cloud",
            "gpt-oss:20b-cloud",
            "deepseek-v3.1:671b-cloud"
        ]
    
    def get_models(self) -> List[str]:
        return self.available_models
    
    def send_message(self, messages: List[Dict], model: str, **kwargs) -> Optional[str]:
        if model not in self.available_models:
            return None
            
        try:
            temperature = kwargs.get('temperature', 0.69)
            top_p = kwargs.get('top_p', 0.7)
            top_k = kwargs.get('top_k', 40)
            typical_p = kwargs.get('typical_p', 0.8)
            num_ctx = kwargs.get('num_ctx', 8192)
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": top_p,
                    "top_k": top_k,
                    "typical_p": typical_p,
                    "num_ctx": num_ctx
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=kwargs.get('timeout', 180)
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['message']['content'].strip()
            else:
                print(f"Ollama error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            print(f"Ollama request failed: {e}")
            return None

class CerebrasProvider(AIProvider):
    def __init__(self, config: Dict = None):
        super().__init__("cerebras", config)
        self.base_url = "https://api.cerebras.ai/v1/chat/completions"
        self.api_key = self._load_api_key()
        self.is_available = bool(self.api_key)
        self.available_models = [
            "qwen-3-235b-a22b-instruct-2507",
            "qwen-3-235b-a22b-thinking-2507",
            "qwen-3-coder-480b",
            "qwen-3-32b",
            "gpt-oss-120b",
            "llama-3.3-70b",
            "llama-4-scout-17b-16e-instruct",
            "llama3.1-8b"
        ]
    
    def _load_api_key(self):
        try:
            api_key = Database.get_api_key('cerebras')
            return api_key
        except Exception as e:
            return None
    
    def get_models(self) -> List[str]:
        return self.available_models
    
    def send_message(self, messages: List[Dict], model: str, **kwargs) -> Optional[str]:
        if not self.api_key or model not in self.available_models:
            return None
        
        try:
            temperature = kwargs.get('temperature', 0.69)
            max_tokens = kwargs.get('max_tokens', 2048)
            top_p = kwargs.get('top_p', 0.7)
            top_k = kwargs.get('top_k', 40)
            typical_p = kwargs.get('typical_p', 0.8)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "top_k": top_k,
                "typical_p": typical_p,
                "stream": False
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=kwargs.get('timeout', 120)
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                print(f"Cerebras API error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"Cerebras request failed: {e}")
        
        return None

class OpenRouterProvider(AIProvider):
    def __init__(self, config: Dict = None):
        super().__init__("openrouter", config)
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.api_key = self._load_api_key()
        self.is_available = bool(self.api_key)
        self.available_models = [
            "tngtech/deepseek-r1t2-chimera:free",
            "z_ai/glm-4.5-air:free",
            "tngtech/deepseek-r1t-chimera:free",
            "deepseek/deepseek-v3:free",
            "deepseek/r1:free",
            "qwen/qwen3-235b-a22b:free",
            "qwen/qwen3-vl-235b-a22b-instruct:free",
            "meituan/longcat-flash-chat:free",
            "openai/gpt-4o-mini:free",
            "google/gemini-flash-1.5-8b:free"
        ]
    
    def _load_api_key(self):
        try:
            api_key = Database.get_api_key('openrouter')
            return api_key
        except Exception as e:
            return None
    
    def get_models(self) -> List[str]:
        return self.available_models
    
    def send_message(self, messages: List[Dict], model: str, **kwargs) -> Optional[str]:
        if not self.api_key or model not in self.available_models:
            return None
        
        try:
            if self.supports_vision(model) and messages:
                last_user_message = self._get_last_user_message(messages)
                if last_user_message and multimodal_tools.has_images(last_user_message):
                    print(f"Formatting vision message for {model}")
                    vision_messages = self.format_vision_message(last_user_message)
                    messages = self._replace_last_user_message(messages, last_user_message, vision_messages)
            
            temperature = kwargs.get('temperature', 0.69)
            max_tokens = kwargs.get('max_tokens', 2048)
            top_p = kwargs.get('top_p', 0.7)
            top_k = kwargs.get('top_k', 40)
            typical_p = kwargs.get('typical_p', 0.8)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/bani/yuzu-companion",
                "X-Title": "Yuzu-Companion"
            }
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "top_k": top_k,
                "typical_p": typical_p,
                "stream": False
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=kwargs.get('timeout', 120)
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                print(f"OpenRouter API error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"OpenRouter request failed: {e}")
        
        return None
    
    def _get_last_user_message(self, messages: List[Dict]) -> Optional[str]:
        for msg in reversed(messages):
            if msg['role'] == 'user':
                return msg['content'] if isinstance(msg['content'], str) else None
        return None
    
    def _replace_last_user_message(self, messages: List[Dict], old_message: str, new_messages: List[Dict]) -> List[Dict]:
        new_message_list = []
        replaced = False
        
        for msg in messages:
            if msg['role'] == 'user' and msg['content'] == old_message and not replaced:
                new_message_list.extend(new_messages)
                replaced = True
            else:
                new_message_list.append(msg)
        
        return new_message_list

class ChutesProvider(AIProvider):
    def __init__(self, config: Dict = None):
        super().__init__("chutes", config)
        self.api_key = self._load_api_key()
        self.is_available = bool(self.api_key)
        self.available_models = [
            "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "deepseek-ai/DeepSeek-V3-0324",
            "deepseek-ai/DeepSeek-V3.1-Terminus", 
            "tngtech/DeepSeek-TNG-R1T-Chimera",
            "tngtech/DeepSeek-TNG-R1T2-Chimera",
            "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "Qwen/Qwen3-235B-A22B-Thinking-2507",
            "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8",
            "zai-org/GLM-4.5-FP8",
            "zai-org/GLM-4.6-FP8",
            "deepseek-ai/DeepSeek-R1"
        ]
    
    def _load_api_key(self):
        try:
            api_key = Database.get_api_key('chutes')
            return api_key
        except Exception as e:
            return None
    
    def get_models(self) -> List[str]:
        return self.available_models
    
    def send_message(self, messages: List[Dict], model: str, **kwargs) -> Optional[str]:
        if not self.api_key or model not in self.available_models:
            return None
        
        try:
            if self.supports_vision(model) and messages:
                last_user_message = self._get_last_user_message(messages)
                if last_user_message and multimodal_tools.has_images(last_user_message):
                    print(f"Formatting vision message for {model}")
                    vision_messages = self.format_vision_message(last_user_message)
                    messages = self._replace_last_user_message(messages, last_user_message, vision_messages)
            
            temperature = kwargs.get('temperature', 0.69)
            max_tokens = kwargs.get('max_tokens', 32768)
            top_p = kwargs.get('top_p', 0.7)
            top_k = kwargs.get('top_k', 40)
            typical_p = kwargs.get('typical_p', 0.8)
            stream = kwargs.get('stream', False)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "top_k": top_k,
                "typical_p": typical_p,
                "stream": stream
            }
            
            response = requests.post(
                "https://llm.chutes.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=kwargs.get('timeout', 120)
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                print(f"Chutes API error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"Chutes request failed: {e}")
        
        return None
    
    def _get_last_user_message(self, messages: List[Dict]) -> Optional[str]:
        for msg in reversed(messages):
            if msg['role'] == 'user':
                return msg['content'] if isinstance(msg['content'], str) else None
        return None
    
    def _replace_last_user_message(self, messages: List[Dict], old_message: str, new_messages: List[Dict]) -> List[Dict]:
        new_message_list = []
        replaced = False
        
        for msg in messages:
            if msg['role'] == 'user' and msg['content'] == old_message and not replaced:
                new_message_list.extend(new_messages)
                replaced = True
            else:
                new_message_list.append(msg)
        
        return new_message_list

class AIProviderManager:
    def __init__(self):
        self.providers = {}
        self.load_providers()
    
    def load_providers(self):
        print("Loading AI providers...")
        
        ollama = OllamaProvider()
        if ollama.test_connection():
            self.providers["ollama"] = ollama
            print("Ollama provider loaded")
        
        cerebras = CerebrasProvider()
        if cerebras.is_available:
            self.providers["cerebras"] = cerebras
            print("Cerebras provider loaded")
        
        openrouter = OpenRouterProvider()
        if openrouter.is_available:
            self.providers["openrouter"] = openrouter
            print("OpenRouter provider loaded")
        
        chutes = ChutesProvider()
        if chutes.is_available:
            self.providers["chutes"] = chutes
            print("Chutes provider loaded")
        
        print(f"Total providers loaded: {list(self.providers.keys())}")
    
    def get_available_providers(self) -> List[str]:
        return list(self.providers.keys())
    
    def get_provider_models(self, provider_name: str) -> List[str]:
        if provider_name in self.providers:
            return self.providers[provider_name].get_models()
        return []
    
    def get_all_models(self) -> Dict[str, List[str]]:
        all_models = {}
        for provider_name, provider in self.providers.items():
            all_models[provider_name] = provider.get_models()
        return all_models
    
    def send_message(self, provider_name: str, model: str, messages: List[Dict], **kwargs) -> Optional[str]:
        if provider_name not in self.providers:
            return None
        
        provider = self.providers[provider_name]
        start_time = time.time()
        response = provider.send_message(messages, model, **kwargs)
        response_time = time.time() - start_time
        
        if response:
            tokens_estimate = len(response) // 4
            throughput = tokens_estimate / response_time if response_time > 0 else 0
            print(f"Response from [{provider_name}/{model} - {response_time:.1f}s - {throughput:.0f} t/s]")
            return response
        else:
            print(f"{provider_name}/{model} failed after {response_time:.1f}s")
            return None

_ai_manager_instance = None

def get_ai_manager():
    global _ai_manager_instance
    if _ai_manager_instance is None:
        _ai_manager_instance = AIProviderManager()
    return _ai_manager_instance

def reload_ai_manager():
    global _ai_manager_instance
    _ai_manager_instance = AIProviderManager()
    return _ai_manager_instance
