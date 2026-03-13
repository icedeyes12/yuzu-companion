# Result Processor Module
# Processes tool results into UI-friendly display format

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum
import json


def escapeHtml(text):
    """Escape HTML entities for safe rendering."""
    return (str(text)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#39;'))


class DisplayType(Enum):
    """Types of UI displays for tool results."""
    LOADING = "loading"          # Tool is running
    IMAGE = "image"             # Image result
    WEATHER_CARD = "weather"    # Weather info card
    SEARCH_RESULTS = "search"   # Web search results
    TEXT = "text"               # Plain text
    JSON = "json"               # Formatted JSON
    ERROR = "error"             # Error message
    COMPACT = "compact"         # Minimal inline display


@dataclass
class ProcessedResult:
    """Result formatted for UI consumption."""
    display_type: DisplayType
    content: Dict[str, Any]  # Display-specific data
    narrative: Optional[str] = None  # LLM-generated narrative (optional)
    tool_visible: bool = False  # Whether to show tool UI or keep hidden
    inline: bool = True  # Show inline vs as separate card


class ResultProcessor:
    """
    Processes tool execution results into UI-ready format.
    
    Handles:
    - Format conversion for different display types
    - Loading state generation
    - Error presentation
    - Narrative generation prompts (not actual generation)
    """
    
    # Tool display configuration
    TOOL_DISPLAY_CONFIG = {
        'image_generate': {
            'display_type': DisplayType.IMAGE,
            'tool_visible': True,  # Show generating animation
            'inline': True,
            'narrative_prompt': "React to this generated image naturally. Don't describe it literally - respond as if you can see it. Keep it brief and warm."
        },
        'imagine': {
            'display_type': DisplayType.IMAGE,
            'tool_visible': True,
            'inline': True,
            'narrative_prompt': "React to this generated image naturally. Don't describe it literally - respond as if you can see it. Keep it brief and warm."
        },
        'weather': {
            'display_type': DisplayType.WEATHER_CARD,
            'tool_visible': False,  # Hide tool, just show answer
            'inline': True,
            'narrative_prompt': "Summarize this weather information in a natural, conversational way. Mention the temperature and conditions briefly."
        },
        'web_search': {
            'display_type': DisplayType.SEARCH_RESULTS,
            'tool_visible': False,
            'inline': False,  # Show as separate card
            'narrative_prompt': "Summarize these search results briefly. Pick the most relevant information and present it naturally."
        },
        'memory_search': {
            'display_type': DisplayType.TEXT,
            'tool_visible': False,
            'inline': True,
            'narrative_prompt': "Answer based on the memory search results. Be conversational and reference relevant past conversations naturally."
        },
        'http_request': {
            'display_type': DisplayType.JSON,
            'tool_visible': False,
            'inline': True,
            'narrative_prompt': "Summarize this API response in natural language. Focus on the key information."
        },
    }
    
    def process(self, tool_name: str, result: Any, status: str,
                execution_time_ms: float = 0) -> ProcessedResult:
        """
        Process tool result into UI format.
        
        Args:
            tool_name: Name of the executed tool
            result: Raw tool result
            status: Execution status (success, error, timeout)
            execution_time_ms: Execution time
            
        Returns:
            ProcessedResult ready for UI
        """
        # Handle error states
        if status == 'error':
            return self._create_error_result(tool_name, result)
        
        if status == 'timeout':
            return self._create_timeout_result(tool_name)
        
        # Get display config
        config = self.TOOL_DISPLAY_CONFIG.get(tool_name, {
            'display_type': DisplayType.TEXT,
            'tool_visible': False,
            'inline': True,
            'narrative_prompt': "Summarize this result briefly."
        })
        
        # Process based on type
        display_type = config['display_type']
        content = self._format_content(display_type, result, tool_name)
        
        return ProcessedResult(
            display_type=display_type,
            content=content,
            narrative=config.get('narrative_prompt'),  # Prompt for LLM, not actual text
            tool_visible=config['tool_visible'],
            inline=config['inline']
        )
    
    def create_loading_state(self, tool_name: str, 
                            detected_intent: Optional[str] = None) -> ProcessedResult:
        """
        Create loading state for tool execution.
        
        Args:
            tool_name: Tool being executed
            detected_intent: What the user wanted (e.g., "image", "weather")
            
        Returns:
            ProcessedResult with loading display
        """
        # Human-friendly descriptions
        descriptions = {
            'image_generate': 'Creating image',
            'imagine': 'Creating image',
            'web_search': 'Searching',
            'weather': 'Checking weather',
            'memory_search': 'Searching memory',
            'http_request': 'Fetching data',
        }
        
        description = descriptions.get(tool_name, f'Running {tool_name}')
        icon = self._get_loading_icon(tool_name)
        
        return ProcessedResult(
            display_type=DisplayType.LOADING,
            content={
                'tool_name': tool_name,
                'description': description,
                'icon': icon,
                'intent': detected_intent,
                'animation': 'spinner'
            },
            tool_visible=True,  # Show loading UI
            inline=True
        )
    
    def format_result(self, tool_name: str, result: Any, status: str,
                     execution_time_ms: float = 0) -> ProcessedResult:
        """Method alias"""
        return self.process(tool_name, result, status, execution_time_ms)
    
    def _format_content(self, display_type: DisplayType, result: Any, 
                        tool_name: str) -> Dict[str, Any]:
        """Format result content based on display type."""
        
        if display_type == DisplayType.IMAGE:
            return self._format_image_result(result)
        
        elif display_type == DisplayType.WEATHER_CARD:
            return self._format_weather_result(result)
        
        elif display_type == DisplayType.SEARCH_RESULTS:
            return self._format_search_result(result)
        
        elif display_type == DisplayType.JSON:
            return self._format_json_result(result)
        
        elif display_type == DisplayType.TEXT:
            return self._format_text_result(result)
        
        else:
            # Fallback
            return {'text': str(result)}
    
    def _format_image_result(self, result: Any) -> Dict[str, Any]:
        """Format image generation result."""
        # Handle different result formats
        if isinstance(result, str):
            # Direct path
            image_path = result
            prompt = None
        elif isinstance(result, dict):
            image_path = result.get('image_path') or result.get('path') or result.get('url')
            prompt = result.get('prompt') or result.get('description')
        else:
            image_path = str(result)
            prompt = None
        
        # Ensure path is web-accessible
        if image_path and image_path.startswith('/static/'):
            web_path = image_path
        elif image_path and image_path.startswith('static/'):
            web_path = '/' + image_path
        elif image_path:
            # Assume it needs static prefix
            web_path = f'/static/generated_images/{image_path}'
        else:
            web_path = None
        
        return {
            'type': 'image',
            'image_url': web_path,
            'image_alt': prompt[:50] if prompt else 'Generated image',
            'prompt': prompt,
            'timestamp': None  # Could add generation timestamp
        }
    
    def _format_weather_result(self, result: Any) -> Dict[str, Any]:
        """Format weather result into card display."""
        if isinstance(result, dict):
            # Assume structured weather data
            return {
                'type': 'weather',
                'location': result.get('location', 'Unknown'),
                'temperature': result.get('temperature'),
                'condition': result.get('condition') or result.get('description'),
                'humidity': result.get('humidity'),
                'wind': result.get('wind_speed') or result.get('wind'),
                'forecast': result.get('forecast', []),
                'icon': result.get('icon', '☀️'),
                'raw': result  # Keep raw for LLM
            }
        else:
            # Plain text weather
            return {
                'type': 'weather',
                'description': str(result),
                'raw': {'description': str(result)}
            }
    
    def _format_search_result(self, result: Any) -> Dict[str, Any]:
        """Format search results."""
        if isinstance(result, list):
            # List of search results
            results = []
            for item in result:
                if isinstance(item, dict):
                    results.append({
                        'title': item.get('title', 'Result'),
                        'snippet': item.get('snippet') or item.get('description') or item.get('content', '')[:200],
                        'url': item.get('url') or item.get('link'),
                        'source': item.get('source', 'Web')
                    })
                else:
                    results.append({
                        'title': 'Result',
                        'snippet': str(item)[:200],
                        'url': None,
                        'source': 'Web'
                    })
            
            return {
                'type': 'search',
                'results': results[:5],  # Limit to top 5
                'total_count': len(result),
                'query': None  # Could be passed from caller
            }
        else:
            # Single text result
            return {
                'type': 'search',
                'results': [{
                    'title': 'Search Result',
                    'snippet': str(result)[:200],
                    'url': None,
                    'source': 'Web'
                }],
                'total_count': 1
            }
    
    def _format_json_result(self, result: Any) -> Dict[str, Any]:
        """Format JSON/API result."""
        if isinstance(result, (dict, list)):
            pretty = json.dumps(result, indent=2, ensure_ascii=False)
            return {
                'type': 'json',
                'formatted': pretty,
                'raw': result,
                'collapsible': True  # Allow expand/collapse
            }
        else:
            return {
                'type': 'json',
                'formatted': str(result),
                'raw': result,
                'collapsible': False
            }
    
    def _format_text_result(self, result: Any) -> Dict[str, Any]:
        """Format plain text result."""
        text = str(result)
        
        # Check if it's actually markdown
        if text.startswith('#') or text.startswith('*') or '```' in text:
            return {
                'type': 'markdown',
                'text': text
            }
        
        return {
            'type': 'text',
            'text': text
        }
    
    def _create_error_result(self, tool_name: str, error: Any) -> ProcessedResult:
        """Create error display."""
        error_msg = str(error) if error else "Unknown error occurred"
        
        # User-friendly error messages
        friendly_errors = {
            'image_generate': "I couldn't generate that image right now.",
            'imagine': "I couldn't create that image right now.",
            'web_search': "I couldn't search the web right now.",
            'weather': "I couldn't check the weather right now.",
            'memory_search': "I couldn't search my memory right now.",
        }
        
        friendly = friendly_errors.get(tool_name, "Something went wrong with that request.")
        
        return ProcessedResult(
            display_type=DisplayType.ERROR,
            content={
                'type': 'error',
                'friendly_message': friendly,
                'technical_message': error_msg,
                'tool_name': tool_name,
                'retryable': True  # Can user retry?
            },
            narrative=f"{friendly} Want me to try again?",
            tool_visible=True,  # Show error in UI
            inline=True
        )
    
    def _create_timeout_result(self, tool_name: str) -> ProcessedResult:
        """Create timeout display."""
        return ProcessedResult(
            display_type=DisplayType.ERROR,
            content={
                'type': 'timeout',
                'friendly_message': "That took too long to complete.",
                'tool_name': tool_name,
                'retryable': True
            },
            narrative="Sorry, that took too long. Want me to try again?",
            tool_visible=True,
            inline=True
        )
    
    def _get_loading_icon(self, tool_name: str) -> str:
        """Get appropriate loading icon for tool."""
        icons = {
            'image_generate': '🖼️',
            'imagine': '🖼️',
            'web_search': '🔍',
            'weather': '🌤️',
            'memory_search': '🧠',
            'http_request': '🌐',
        }
        return icons.get(tool_name, '⏳')
    
    def generate_narrative_prompt(self, tool_name: str, result: ProcessedResult) -> str:
        """
        Generate prompt for LLM to create natural response.
        
        This returns a prompt that the LLM can use to generate
        a natural response, not the actual narrative itself.
        """
        config = self.TOOL_DISPLAY_CONFIG.get(tool_name, {})
        base_prompt = config.get('narrative_prompt', 'Summarize this result.')
        
        # Add context about what was found
        if result.display_type == DisplayType.IMAGE:
            return f"{base_prompt}\n\nThe image has been generated successfully and is now visible above."
        
        elif result.display_type == DisplayType.WEATHER_CARD:
            weather = result.content
            return f"{base_prompt}\n\nWeather data: {weather.get('condition')}, {weather.get('temperature')} in {weather.get('location')}."
        
        elif result.display_type == DisplayType.SEARCH_RESULTS:
            results = result.content.get('results', [])
            summary = f"{base_prompt}\n\nFound {len(results)} results. Key findings:\n"
            for i, r in enumerate(results[:3], 1):
                summary += f"{i}. {r.get('title')}: {r.get('snippet')[:100]}...\n"
            return summary
        
        else:
            return f"{base_prompt}\n\nResult: {result.content.get('text', str(result.content))[:200]}"
