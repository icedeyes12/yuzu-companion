"""
IntentDetector - Determines if user request needs a tool

Uses LLM-based detection with structured output to determine:
- Whether a tool is needed
- Which tool to use
- What parameters to pass
- Confidence level of the detection
"""

import json
import re
from typing import Optional, Dict, Any, List
from database import Database


class ToolIntent:
    """Represents a detected tool intent from user message"""
    def __init__(
        self,
        tool_name: str,
        params: Dict[str, Any],
        confidence: float,
        reasoning: str,
        tool_type: str = "internal"
    ):
        self.tool_name = tool_name
        self.params = params
        self.confidence = confidence
        self.reasoning = reasoning
        self.tool_type = tool_type  # 'internal' or 'mcp'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "tool_type": self.tool_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolIntent":
        return cls(
            tool_name=data.get("tool_name", ""),
            params=data.get("params", {}),
            confidence=data.get("confidence", 0.0),
            reasoning=data.get("reasoning", ""),
            tool_type=data.get("tool_type", "internal")
        )


class IntentDetector:
    """
    LLM-based intent detection for tool execution.
    
    Analyzes user messages to determine if a tool should be invoked,
    and if so, which tool and with what parameters.
    """
    
    # Tool definitions for the LLM to understand available tools
    TOOL_DEFINITIONS = {
        "image_generate": {
            "description": "Generate images from text descriptions",
            "keywords": ["generate", "create image", "draw", "imagine", " buat gambar", "gambar", 
                        "picture", "photo", "create picture", "make image", "draw image", "make a picture",
                        "buatkan gambar", "gambarIN", "img"],
            "params": {"prompt": "str"}
        },
        "request": {
            "description": "Fetch data from URLs, APIs, or web pages",
            "keywords": ["fetch", "request", "get data", "api", "weather", "search",
                        "http://", "https://", "get ", "buka ", "open "],
            "params": {"url": "str", "method": "str"}
        },
        "memory_search": {
            "description": "Search through conversation history and memories",
            "keywords": ["remember", "search memory", "apa yang kamu ingat", "cari"],
            "params": {"query": "str"}
        },
        "memory_sql": {
            "description": "Query structured data in memory database",
            "keywords": ["query", "sql", "database", "select"],
            "params": {"query": "str"}
        },
        "image_analyze": {
            "description": "Analyze images to describe their contents",
            "keywords": ["describe", "analyze image", "lihat gambar", "apa ini"],
            "params": {"image_path": "str"}
        },
        # MCP Memory Tools (MCP:memory:tool_name format)
        "MCP:memory:search_nodes": {
            "description": "Search nodes in memory graph by query",
            "keywords": ["search memory", "cari memori", "find in memory", "search nodes"],
            "params": {"query": "str"},
            "mcp_format": True
        },
        "MCP:memory:get_entity": {
            "description": "Get specific entity from memory by name",
            "keywords": ["get entity", "read entity", "fetch memory", "lihat memori"],
            "params": {"entity_name": "str"},
            "mcp_format": True
        },
        "MCP:memory:create_entities": {
            "description": "Create new entities in memory graph",
            "keywords": ["create memory", "add entity", "buat memori", "new memory"],
            "params": {"entities": "list"},
            "mcp_format": True
        },
        "MCP:memory:add_observations": {
            "description": "Add observations to existing memory entities",
            "keywords": ["add observation", "update memory", "tambah memori"],
            "params": {"entity_name": "str", "observations": "list"},
            "mcp_format": True
        }
    }
    
    # Confidence threshold for auto-execution
    CONFIDENCE_THRESHOLD = 0.7
    
    def __init__(self, ai_manager=None):
        self.ai_manager = ai_manager
    
    def _build_detection_prompt(self, user_message: str, conversation_context: List[Dict]) -> str:
        """Build prompt for LLM-based intent detection"""
        
        # Format conversation context (last 3 messages)
        context_str = ""
        if conversation_context:
            context_lines = []
            for msg in conversation_context[-3:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:200]  # Truncate long messages
                context_lines.append(f"{role}: {content}")
            context_str = "\n".join(context_lines)
        
        # Build tool descriptions
        tool_descs = []
        for tool_name, tool_info in self.TOOL_DEFINITIONS.items():
            keywords = ", ".join(tool_info["keywords"])
            tool_descs.append(f"- {tool_name}: {tool_info['description']} (keywords: {keywords})")
        
        tools_str = "\n".join(tool_descs)
        
        prompt = f"""You are an intent detector for a AI companion assistant.

CURRENT MESSAGE:
{user_message}

CONVERSATION CONTEXT:
{context_str}

AVAILABLE TOOLS:
{tools_str}

TASK:
Analyze the user's message to determine if they want to use a tool.
Output a JSON object with your decision.

OUTPUT FORMAT:
{{
    "needs_tool": true or false,
    "tool_name": "name of tool to use" or null,
    "params": {{"param_name": "param_value"}},
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation of your decision"
}}

RULES:
1. If the user is asking for image generation, use "image_generate" with the prompt as params.prompt
2. If the user wants to fetch data from a URL, use "request" with params.url
3. If the user asks to remember or search memories, use "memory_search"
4. If the user wants to query a database, use "memory_sql"
5. If the user wants to analyze an image, use "image_analyze"
6. Only return needs_tool=true if there's a clear intent to use a specific tool
7. If the message is a general conversation, question, or doesn't clearly need a tool, return needs_tool=false

Respond with ONLY the JSON object, no other text."""
        
        return prompt
    
    def _parse_llm_response(self, response: str) -> Optional[ToolIntent]:
        """Parse LLM response to extract tool intent"""
        try:
            # Try to extract JSON from response
            # First try direct parse
            try:
                data = json.loads(response.strip())
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code block
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                else:
                    # Try to find JSON-like structure
                    match = re.search(r'\{.*\}', response, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))
                    else:
                        return None
            
            if not data.get("needs_tool", False):
                return None
            
            tool_name = data.get("tool_name")
            if not tool_name:
                return None
            
            # Validate tool exists
            if tool_name not in self.TOOL_DEFINITIONS:
                return None
            
            return ToolIntent(
                tool_name=tool_name,
                params=data.get("params", {}),
                confidence=data.get("confidence", 0.0),
                reasoning=data.get("reasoning", ""),
                tool_type="internal"  # Default to internal, MCP would be detected separately
            )
            
        except Exception as e:
            print(f"[IntentDetector] Failed to parse LLM response: {e}")
            return None
    
    def _keyword_based_detection(self, user_message: str) -> Optional[ToolIntent]:
        """
        Fallback keyword-based detection when LLM is unavailable.
        Quick heuristic for common tool patterns.
        """
        message_lower = user_message.lower().strip()
        
        # Command prefix patterns (/imagine, /request, etc)
        if user_message.strip().startswith("/"):
            parts = user_message.strip().split(None, 1)  # Split on first whitespace
            cmd = parts[0][1:]  # Remove leading /
            args = parts[1] if len(parts) > 1 else ""
            
            if cmd in ["imagine", "image_generate", "generate", "draw"]:
                return ToolIntent(
                    tool_name="image_generate",
                    params={"prompt": args},
                    confidence=0.95,
                    reasoning="Command prefix detected"
                )
            elif cmd in ["request", "fetch", "get", "open"]:
                return ToolIntent(
                    tool_name="request",
                    params={"url": args},
                    confidence=0.95,
                    reasoning="Command prefix detected"
                )
            elif cmd in ["memory_search", "remember", "search"]:
                return ToolIntent(
                    tool_name="memory_search",
                    params={"query": args},
                    confidence=0.95,
                    reasoning="Command prefix detected"
                )
        
        # Image generation patterns - order matters! Check longer phrases first
        image_keywords = [
            # Longer phrases first
            "create picture", "make picture", "make a picture", "draw image",
            # Then shorter
            "generate", "create image", "draw", "imagine", " buat ", "gambar", " buat gambar",
            "photo", "take a photo", "make image"
        ]
        for kw in image_keywords:
            if kw in message_lower:
                # Extract prompt (everything after keyword)
                idx = message_lower.find(kw)
                prompt = user_message[idx + len(kw):].strip()
                # If no significant prompt after keyword, use the original message
                if not prompt or len(prompt) < 2:
                    prompt = user_message.replace(kw, "", 1).strip()
                # Even if prompt is empty, return the intent - user wants to generate an image
                return ToolIntent(
                    tool_name="image_generate",
                    params={"prompt": prompt or "a beautiful image"},
                    confidence=0.85,
                    reasoning="Keyword match for image generation"
                )
        
        # URL fetch patterns (http/https in message)
        if "http://" in message_lower or "https://" in message_lower:
            # Extract URL
            url_match = re.search(r'https?://[^\s]+', user_message)
            if url_match:
                return ToolIntent(
                    tool_name="request",
                    params={"url": url_match.group(0)},
                    confidence=0.9,
                    reasoning="URL detected in message"
                )
        
        # Fetch keyword
        if message_lower.startswith("fetch "):
            url = user_message[6:].strip()
            return ToolIntent(
                tool_name="request",
                params={"url": url},
                confidence=0.9,
                reasoning="Fetch command detected"
            )
        
        # Memory search patterns
        memory_keywords = ["remember", "cari ingatan", "apa yang kamu ingat", "search memory", "what do you remember"]
        for kw in memory_keywords:
            if kw in message_lower:
                query = user_message.lower().replace(kw, "").strip()
                return ToolIntent(
                    tool_name="memory_search",
                    params={"query": query or user_message},
                    confidence=0.7,
                    reasoning="Keyword match for memory search"
                )
        
        return None
    
    def detect(
        self, 
        user_message: str, 
        conversation_context: List[Dict] = None,
        use_llm: bool = True
    ) -> Optional[ToolIntent]:
        """
        Detect tool intent from user message.
        
        Args:
            user_message: The user's input message
            conversation_context: Previous messages for context
            use_llm: Whether to use LLM detection (fallback to keywords if False)
        
        Returns:
            ToolIntent if tool is needed, None otherwise
        """
        if not user_message or not user_message.strip():
            return None
        
        conversation_context = conversation_context or []
        
        # Try keyword-based detection first (fast)
        keyword_intent = self._keyword_based_detection(user_message)
        if keyword_intent and keyword_intent.confidence >= 0.8:
            print(f"[IntentDetector] Keyword detection: {keyword_intent.tool_name}")
            return keyword_intent
        
        # Try LLM-based detection if enabled
        if use_llm and self.ai_manager:
            try:
                prompt = self._build_detection_prompt(user_message, conversation_context)
                
                # Call LLM
                response = self.ai_manager.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1  # Low temp for consistent detection
                )
                
                if response:
                    intent = self._parse_llm_response(response)
                    if intent and intent.confidence >= self.CONFIDENCE_THRESHOLD:
                        print(f"[IntentDetector] LLM detection: {intent.tool_name} (confidence: {intent.confidence})")
                        return intent
                    elif intent:
                        print(f"[IntentDetector] LLM detection below threshold: {intent.confidence}")
                        
            except Exception as e:
                print(f"[IntentDetector] LLM detection failed: {e}")
        
        # Fallback to keyword detection
        if keyword_intent:
            print(f"[IntentDetector] Falling back to keyword detection: {keyword_intent.tool_name}")
            return keyword_intent
        
        return None


# Singleton instance
_intent_detector = None

def get_intent_detector(ai_manager=None) -> IntentDetector:
    """Get or create IntentDetector singleton"""
    global _intent_detector
    if _intent_detector is None:
        _intent_detector = IntentDetector(ai_manager)
    return _intent_detector
