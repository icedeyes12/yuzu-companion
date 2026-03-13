# Intent Detector Module
# Detects if user input requires tool execution

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class ToolIntent(Enum):
    """Types of tool intents that can be detected."""
    NONE = "none"                    # No tool needed
    IMAGE_GENERATE = "image_generate"  # User wants an image
    WEB_SEARCH = "web_search"          # User wants current info
    WEATHER = "weather"                # User asks about weather
    MEMORY_QUERY = "memory_query"      # User asks about past conversations
    HTTP_REQUEST = "http_request"      # General API/web call
    MCP_TOOL = "mcp_tool"              # External MCP tool


@dataclass
class DetectedIntent:
    """Result of intent detection."""
    intent: ToolIntent
    confidence: float  # 0.0 to 1.0
    tool_name: Optional[str] = None
    suggested_params: Dict[str, Any] = None
    reasoning: str = ""  # Why this intent was detected


class IntentDetector:
    """
    Detects if user input requires tool execution.
    
    Uses pattern matching + LLM-based detection for ambiguous cases.
    """
    
    # Pattern-based detection rules
    PATTERNS = {
        ToolIntent.IMAGE_GENERATE: [
            r'\b(send|create|generate|make|draw)\s+(me\s+)?(a\s+)?(picture|image|photo|pic|drawing)',
            r'\bshow\s+me\s+(a\s+)?(picture|image|photo|pic)',
            r'\bwhat\s+(do|would)\s+you\s+look\s+like',
            r'\b(can\s+you\s+)?(draw|paint|sketch)\b',
            r'/imagine\b',
            r'\byour\s+(picture|photo|image|pic)\b',  # Matches "your picture"
            r'\bsend\s+me\s+your\s+(picture|photo|image)\b',  # Matches "send me your picture"
        ],
        ToolIntent.WEB_SEARCH: [
            r'\b(search|look\s+up|find|google)\s+(for\s+)?(.+)',
            r'\bwhat\s+(is|are)\s+the\s+latest',
            r'\bcurrent\s+(news|events|status)',
            r'\bwho\s+(is|was)\s+(.+)\?',  # Person lookup
            r'\bwhen\s+did\s+(.+)\s+happen',
        ],
        ToolIntent.WEATHER: [
            r'\bweather\b',
            r'\btemperature\b',
            r'\bis\s+it\s+(rain|sunny|cloudy|hot|cold|warm)',
            r'\bforecast\b',
            r'\bwill\s+it\s+rain',
        ],
        ToolIntent.MEMORY_QUERY: [
            r'\bwhat\s+did\s+(i\s+)?say\s+(about|regarding)\b',
            r'\bremember\s+(when|that)\s+we\s+talked\s+about\b',
            r'\bwhat\s+was\s+our\s+conversation\s+about\b',
            r'\bsearch\s+(my\s+)?memory\b',
            r'\bfind\s+(in\s+)?(our\s+)?(chat|conversation|history)\b',
            r'\bwhat\s+did\s+we\s+talk\s+about\b',  # Simpler pattern for TC5
            r'\bwhat\s+did\s+we\s+discuss\b',  # Another variation
        ],
    }
    
    def __init__(self):
        self._compiled_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[ToolIntent, list]:
        """Compile regex patterns for performance."""
        compiled = {}
        for intent, patterns in self.PATTERNS.items():
            compiled[intent] = [re.compile(p, re.IGNORECASE) for p in patterns]
        return compiled
    
    def detect(self, user_input: str, context: Optional[Dict] = None) -> DetectedIntent:
        """
        Detect if user input requires tool execution.
        
        Args:
            user_input: Raw user input text
            context: Optional conversation context
            
        Returns:
            DetectedIntent with intent type and confidence
        """
        # Normalize input
        normalized = user_input.lower().strip()
        
        # Check for explicit command prefix (e.g., /imagine, /search)
        explicit_intent = self._check_explicit_command(normalized)
        if explicit_intent:
            return explicit_intent
        
        # Pattern-based detection
        pattern_match = self._pattern_detection(normalized)
        if pattern_match.confidence >= 0.8:
            return pattern_match
        
        # Check for ambiguous cases that need LLM verification
        if pattern_match.confidence >= 0.4:
            return self._llm_verify(normalized, pattern_match)
        
        # No tool needed
        return DetectedIntent(
            intent=ToolIntent.NONE,
            confidence=1.0,
            reasoning="No tool patterns matched"
        )
    
    def _check_explicit_command(self, normalized: str) -> Optional[DetectedIntent]:
        """Check for explicit /command prefixes."""
        commands = {
            '/imagine': (ToolIntent.IMAGE_GENERATE, 'image_generate'),
            '/image': (ToolIntent.IMAGE_GENERATE, 'image_generate'),
            '/search': (ToolIntent.WEB_SEARCH, 'web_search'),
            '/weather': (ToolIntent.WEATHER, 'weather'),
            '/memory': (ToolIntent.MEMORY_QUERY, 'memory_search'),
            '/request': (ToolIntent.HTTP_REQUEST, 'http_request'),
        }
        
        for cmd, (intent, tool) in commands.items():
            if normalized.startswith(cmd):
                # Extract parameters after command
                params = normalized[len(cmd):].strip()
                return DetectedIntent(
                    intent=intent,
                    confidence=1.0,
                    tool_name=tool,
                    suggested_params={'query': params} if params else {},
                    reasoning=f"Explicit command: {cmd}"
                )
        
        return None
    
    def _pattern_detection(self, normalized: str) -> DetectedIntent:
        """Pattern-based intent detection."""
        scores = []
        
        for intent, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(normalized):
                    match = pattern.search(normalized)
                    # Extract matched groups as suggested params
                    groups = match.groups() if match.lastindex else ()
                    
                    # Higher score for longer/more specific matches
                    match_length = len(match.group(0))
                    confidence = min(0.6 + (match_length / 100), 0.95)
                    
                    scores.append((
                        intent,
                        confidence,
                        self._extract_params(intent, groups, normalized)
                    ))
        
        if scores:
            # Return highest confidence match
            best = max(scores, key=lambda x: x[1])
            return DetectedIntent(
                intent=best[0],
                confidence=best[1],
                tool_name=self._intent_to_tool(best[0]),
                suggested_params=best[2],
                reasoning=f"Pattern match: {best[0].value}"
            )
        
        return DetectedIntent(
            intent=ToolIntent.NONE,
            confidence=0.0,
            reasoning="No patterns matched"
        )
    
    def _extract_params(self, intent: ToolIntent, groups: tuple, full_text: str) -> Dict[str, Any]:
        """Extract suggested parameters from matched groups."""
        params = {}
        
        if intent == ToolIntent.IMAGE_GENERATE:
            # Remove trigger words, keep the description
            desc = full_text
            for trigger in ['send me', 'create', 'generate', 'make', 'draw', 'a picture', 'an image', 'of']:
                desc = desc.replace(trigger, '').strip()
            params['prompt'] = desc
            
        elif intent == ToolIntent.WEB_SEARCH:
            # Use captured groups or full text
            if groups:
                params['query'] = ' '.join(g for g in groups if g)
            else:
                params['query'] = full_text
                
        elif intent == ToolIntent.WEATHER:
            # Check if location mentioned
            location_match = re.search(r'\bin\s+([A-Za-z\s]+)', full_text)
            if location_match:
                params['location'] = location_match.group(1).strip()
            else:
                params['location'] = 'current'  # Use user's saved location
                
        elif intent == ToolIntent.MEMORY_QUERY:
            # Extract search terms
            params['query'] = full_text
            
        return params
    
    def _intent_to_tool(self, intent: ToolIntent) -> Optional[str]:
        """Map intent to specific tool name."""
        mapping = {
            ToolIntent.IMAGE_GENERATE: 'image_generate',
            ToolIntent.WEB_SEARCH: 'web_search',
            ToolIntent.WEATHER: 'weather',
            ToolIntent.MEMORY_QUERY: 'memory_search',
            ToolIntent.HTTP_REQUEST: 'http_request',
        }
        return mapping.get(intent)
    
    def _llm_verify(self, normalized: str, preliminary: DetectedIntent) -> DetectedIntent:
        """
        Use LLM to verify ambiguous pattern matches.
        
        This is a lightweight check for cases where pattern matching
        is uncertain. Can be skipped if no LLM is available.
        """
        # For now, trust the pattern match if confidence >= 0.5
        # In production, this could call a small classifier model
        if preliminary.confidence >= 0.5:
            return preliminary
        
        # Otherwise, downgrade to NONE
        return DetectedIntent(
            intent=ToolIntent.NONE,
            confidence=0.0,
            reasoning=f"Pattern match confidence too low: {preliminary.confidence}"
        )
