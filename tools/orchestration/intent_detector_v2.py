# Intent Detector Module V2
# LLM-based tool intent detection per roadmap spec

import json
import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from database import Database


@dataclass
class ToolIntent:
    """
    Output of intent detection per roadmap spec.
    
    Roadmap Reference: Phase 2.2.A
    """
    tool_name: str
    params: Dict[str, Any]
    confidence: float  # 0.0 - 1.0
    reasoning: str
    tool_type: str = "internal"  # 'internal' | 'mcp_stdio' | 'mcp_http'


class IntentDetector:
    """
    Determine if user request needs a tool using LLM.
    
    Roadmap: Phase 2.2.A - "LLM prompt with few-shot examples, Structured output (JSON), Confidence threshold: 0.7"
    """
    
    # Available tools for LLM context
    AVAILABLE_TOOLS = [
        {
            "name": "image_generate",
            "description": "Generate images from text descriptions",
            "params": {"prompt": "string - detailed image description"},
            "example_inputs": ["send me your picture", "create an image of a cat"]
        },
        {
            "name": "weather",
            "description": "Get current weather for a location",
            "params": {"location": "string - city name or coordinates"},
            "example_inputs": ["what's the weather", "weather in Tokyo"]
        },
        {
            "name": "web_search",
            "description": "Search the web for information",
            "params": {"query": "string - search terms"},
            "example_inputs": ["search for python tutorials", "find news about AI"]
        },
        {
            "name": "memory_search",
            "description": "Search conversation history",
            "params": {"query": "string - what to find in memories"},
            "example_inputs": ["what did I say yesterday", "remember my birthday"]
        }
    ]
    
    CONFIDENCE_THRESHOLD = 0.7
    
    def __init__(self, ai_manager=None):
        self.ai_manager = ai_manager
        self._intent_cache = {}  # message_hash -> ToolIntent
    
    def detect(self, user_message: str, context: Optional[List[Dict]] = None) -> Optional[ToolIntent]:
        """
        Detect if user message requires tool execution.
        
        Args:
            user_message: Raw user input
            context: Last 3 messages for context
            
        Returns:
            ToolIntent if tool needed, None if direct response sufficient
        """
        # Check cache first
        msg_hash = hash(user_message)
        if msg_hash in self._intent_cache:
            return self._intent_cache[msg_hash]
        
        # Build LLM prompt with few-shot examples (per roadmap)
        prompt = self._build_detection_prompt(user_message, context)
        
        # Call LLM for structured output
        llm_response = self._call_llm_for_intent(prompt)
        
        if not llm_response:
            return None
        
        # Parse structured output
        try:
            result = json.loads(llm_response)
            
            confidence = result.get('confidence', 0.0)
            
            # Below threshold = no tool needed
            if confidence < self.CONFIDENCE_THRESHOLD:
                return None
            
            intent = ToolIntent(
                tool_name=result.get('tool_name', ''),
                params=result.get('params', {}),
                confidence=confidence,
                reasoning=result.get('reasoning', ''),
                tool_type=result.get('tool_type', 'internal')
            )
            
            # Cache result
            self._intent_cache[msg_hash] = intent
            
            return intent
            
        except json.JSONDecodeError:
            print(f"[IntentDetector] Failed to parse LLM response: {llm_response[:200]}")
            return None
    
    def _build_detection_prompt(self, user_message: str, context: Optional[List[Dict]]) -> str:
        """Build prompt for LLM intent detection with few-shot examples."""
        
        # Build context string
        context_str = ""
        if context:
            for msg in context[-3:]:  # Last 3 messages per roadmap
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:100]  # Truncate
                context_str += f"{role}: {content}\n"
        
        # Available tools JSON
        tools_json = json.dumps(self.AVAILABLE_TOOLS, indent=2)
        
        prompt = f"""You are a tool intent detector. Determine if the user's message requires a tool to be executed.

Available Tools:
{tools_json}

Recent Conversation:
{context_str}

Current User Message: "{user_message}"

Analyze if this message requires a tool. Respond with JSON:
{{
    "needs_tool": true/false,
    "tool_name": "name of tool if needed",
    "tool_type": "internal" | "mcp_stdio" | "mcp_http",
    "params": {{"param_name": "extracted value"}},
    "confidence": 0.0-1.0,
    "reasoning": "why this tool is needed"
}}

Confidence Guidelines:
- 0.9-1.0: Explicit command ("search for...", "generate image of...")
- 0.7-0.9: Clear implicit need ("what's the weather" → weather tool)
- 0.5-0.7: Ambiguous, could use tool or direct answer
- 0.0-0.5: Direct question, no tool needed

Respond with JSON only:"""
        
        return prompt
    
    def _call_llm_for_intent(self, prompt: str) -> Optional[str]:
        """Call LLM for intent detection. Uses small/fast model."""
        try:
            # Use existing AI manager if available
            if self.ai_manager:
                profile = Database.get_profile()
                providers_config = profile.get('providers_config', {})
                provider = providers_config.get('preferred_provider', 'ollama')
                model = providers_config.get('preferred_model', 'qwen3-32b')
                
                messages = [
                    {"role": "system", "content": "You are a tool detection system. Respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ]
                
                response = self.ai_manager.send_message(
                    provider_name=provider,
                    model=model,
                    messages=messages,
                    temperature=0.1,  # Low temp for deterministic output
                    max_tokens=500
                )
                
                # Extract JSON from response
                return self._extract_json(response)
            
            # Fallback: use simple pattern matching for development
            return self._fallback_detection(prompt)
            
        except Exception as e:
            print(f"[IntentDetector] LLM call failed: {e}")
            return self._fallback_detection(prompt)
    
    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from LLM response."""
        # Try to find JSON block
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group()
        return text if text.strip().startswith('{') else None
    
    def _fallback_detection(self, prompt: str) -> Optional[str]:
        """Fallback pattern-based detection when LLM unavailable."""
        # Extract user message from prompt
        match = re.search(r'Current User Message: "([^"]+)"', prompt)
        if not match:
            return None
        
        message = match.group(1).lower()
        
        # Simple pattern matching (roadmap allows fallback)
        patterns = {
            'image_generate': [
                (r'\b(send|give|show)\s+(me\s+)?(your|a|an)\s+(picture|photo|image|pic)\b', 0.9),
                (r'\b(generate|create|make)\s+(an?\s+)?image\b', 0.95),
                (r'\b(draw|paint|sketch)\b', 0.85),
            ],
            'weather': [
                (r'\bweather\b', 0.8),
                (r'\b(temperature|forecast|rain|sunny)\b', 0.75),
            ],
            'web_search': [
                (r'\b(search|look\s+up|find)\s+(for\s+)?\b', 0.85),
                (r'\b(what|who|where|when|why|how)\b.*\?', 0.6),
            ],
            'memory_search': [
                (r'\b(remember|recall|what\s+did\s+I|search\s+memory)\b', 0.8),
                (r'\b(tell\s+me\s+about|earlier\s+you\s+said)\b', 0.75),
            ]
        }
        
        for tool_name, tool_patterns in patterns.items():
            for pattern, confidence in tool_patterns:
                if re.search(pattern, message):
                    result = {
                        "needs_tool": True,
                        "tool_name": tool_name,
                        "tool_type": "internal",
                        "params": self._extract_params(tool_name, message),
                        "confidence": confidence,
                        "reasoning": f"Pattern match: {pattern}"
                    }
                    return json.dumps(result)
        
        # No tool needed
        return json.dumps({
            "needs_tool": False,
            "confidence": 0.0,
            "reasoning": "No matching tool pattern"
        })
    
    def _extract_params(self, tool_name: str, message: str) -> Dict[str, Any]:
        """Extract parameters from message for specific tool."""
        params = {}
        
        if tool_name == 'image_generate':
            # Try to extract prompt
            patterns = [
                r'(?:generate|create|make|draw|paint)\s+(?:an?\s+)?(?:image\s+(?:of\s+)?)?["\']?([^"\']+)["\']?',
                r'(?:send|give|show)\s+(?:me\s+)?(?:an?\s+)?(?:picture|photo|image)\s+(?:of\s+)?["\']?([^"\']+)["\']?',
            ]
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    params['prompt'] = match.group(1).strip()
                    break
            if not params.get('prompt'):
                params['prompt'] = message  # Use whole message as prompt
                
        elif tool_name == 'weather':
            # Try to extract location
            match = re.search(r'weather\s+(?:in|at|for)\s+([a-z\s]+?)(?:\?|$|\s)', message, re.IGNORECASE)
            if match:
                params['location'] = match.group(1).strip()
            else:
                params['location'] = 'current'  # Use current location
                
        elif tool_name == 'web_search':
            # Extract search query
            match = re.search(r'(?:search|look\s+up|find)\s+(?:for\s+)?["\']?([^"\']+)["\']?', message, re.IGNORECASE)
            if match:
                params['query'] = match.group(1).strip()
            else:
                # Remove question words for search
                query = re.sub(r'^(what|who|where|when|why|how)\s+(is|are|was|were|did|do|does)\s+', '', message, flags=re.IGNORECASE)
                params['query'] = query.strip(' ?')
                
        elif tool_name == 'memory_search':
            # Extract what to search for
            match = re.search(r'(?:remember|recall|what\s+did\s+I|search\s+memory)\s+(?:about\s+)?["\']?([^"\']+)["\']?', message, re.IGNORECASE)
            if match:
                params['query'] = match.group(1).strip()
            else:
                params['query'] = message
        
        return params