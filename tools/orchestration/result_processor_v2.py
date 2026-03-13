# Result Processor Module V2
# Transforms output to UI-ready ToolCardSpec per roadmap

import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class CardType(Enum):
    """Card types per roadmap spec."""
    LOADING = "loading"
    IMAGE = "image"
    TEXT = "text"
    LIST = "list"
    CODE = "code"
    ERROR = "error"


@dataclass
class ToolCardSpec:
    """
    UI specification object per roadmap Phase 2.2.C.
    
    This is what the frontend ToolCard component consumes.
    """
    card_type: CardType
    header_icon: str  # emoji
    header_title: str
    content: Dict[str, Any]  # rendered content
    llm_commentary: Optional[str] = None  # prompt for LLM, not actual text
    raw_result: Dict[str, Any] = field(default_factory=dict)  # for DB storage
    tool_visible: bool = True
    inline: bool = True


class ResultProcessor:
    """
    Process raw tool output into UI-ready ToolCardSpec.
    
    Roadmap: Phase 2.2.C - "Transform raw output to UI-ready format"
    """
    
    # Tool display configuration per roadmap
    TOOL_CONFIG = {
        'image_generate': {
            'card_type': CardType.IMAGE,
            'header_icon': '🖼️',
            'header_title': 'Image Generation',
            'tool_visible': True,
            'inline': True,
            'llm_commentary_template': "React naturally to this generated image. Don't describe it literally - respond as if seeing it. Keep warm and brief."
        },
        'imagine': {
            'card_type': CardType.IMAGE,
            'header_icon': '🖼️',
            'header_title': 'Image Generation',
            'tool_visible': True,
            'inline': True,
            'llm_commentary_template': "React naturally to this generated image. Don't describe it literally - respond as if seeing it. Keep warm and brief."
        },
        'weather': {
            'card_type': CardType.TEXT,
            'header_icon': '🌤️',
            'header_title': 'Weather',
            'tool_visible': False,  # Hide tool, show answer only
            'inline': True,
            'llm_commentary_template': "Summarize this weather in natural conversation. Mention temp and conditions briefly."
        },
        'web_search': {
            'card_type': CardType.LIST,
            'header_icon': '🔍',
            'header_title': 'Web Search',
            'tool_visible': False,
            'inline': False,  # Full-width card
            'llm_commentary_template': "Summarize these search results. Pick most relevant info, present naturally."
        },
        'memory_search': {
            'card_type': CardType.TEXT,
            'header_icon': '🧠',
            'header_title': 'Memory Search',
            'tool_visible': False,
            'inline': True,
            'llm_commentary_template': "Answer based on memory results. Be conversational, reference past naturally."
        },
        'http_request': {
            'card_type': CardType.CODE,
            'header_icon': '🌐',
            'header_title': 'Web Request',
            'tool_visible': False,
            'inline': True,
            'llm_commentary_template': "Summarize this API response in natural language. Focus on key information."
        }
    }
    
    def process(self, tool_type: str, tool_name: str, status: str,
                result: Any, execution_time_ms: float = 0) -> ToolCardSpec:
        """
        Process tool result into ToolCardSpec.
        
        Args:
            tool_type: 'internal' | 'mcp_stdio' | 'mcp_http'
            tool_name: Name of the tool
            status: 'success' | 'error' | 'timeout'
            result: Raw tool output
            execution_time_ms: Execution time
            
        Returns:
            ToolCardSpec ready for UI rendering
        """
        # Get config for this tool
        config = self.TOOL_CONFIG.get(tool_name, {
            'card_type': CardType.TEXT,
            'header_icon': '🔧',
            'header_title': tool_name.replace('_', ' ').title(),
            'tool_visible': True,
            'inline': True,
            'llm_commentary_template': 'Summarize this result briefly.'
        })
        
        # Handle error states
        if status == 'error':
            return self._create_error_spec(tool_name, result, config)
        
        if status == 'timeout':
            return self._create_timeout_spec(tool_name, config)
        
        # Process based on card type
        card_type = config['card_type']
        
        if card_type == CardType.IMAGE:
            content = self._format_image_content(result, tool_name)
        elif card_type == CardType.TEXT:
            content = self._format_text_content(result)
        elif card_type == CardType.LIST:
            content = self._format_list_content(result)
        elif card_type == CardType.CODE:
            content = self._format_code_content(result)
        else:
            content = {'text': str(result)}
        
        # Build raw result for storage
        raw_result = {
            'tool_type': tool_type,
            'tool_name': tool_name,
            'status': status,
            'result': result,
            'execution_time_ms': execution_time_ms
        }
        
        return ToolCardSpec(
            card_type=card_type,
            header_icon=config['header_icon'],
            header_title=config['header_title'],
            content=content,
            llm_commentary=config['llm_commentary_template'],
            raw_result=raw_result,
            tool_visible=config['tool_visible'],
            inline=config['inline']
        )
    
    def create_loading_spec(self, tool_name: str, detected_intent: Optional[str] = None) -> ToolCardSpec:
        """Create loading state ToolCardSpec."""
        config = self.TOOL_CONFIG.get(tool_name, {
            'header_icon': '⏳',
            'header_title': tool_name.replace('_', ' ').title()
        })
        
        descriptions = {
            'image_generate': 'Creating image',
            'imagine': 'Creating image',
            'web_search': 'Searching',
            'weather': 'Checking weather',
            'memory_search': 'Searching memory',
            'http_request': 'Fetching data',
        }
        
        return ToolCardSpec(
            card_type=CardType.LOADING,
            header_icon=config.get('header_icon', '⏳'),
            header_title=config.get('header_title', tool_name),
            content={
                'description': descriptions.get(tool_name, f'Running {tool_name}'),
                'intent': detected_intent,
                'animation': 'spinner'
            },
            tool_visible=True,
            inline=True
        )
    
    def _format_image_content(self, result: Any, tool_name: str) -> Dict[str, Any]:
        """Format image result."""
        image_path = None
        prompt = None
        
        if isinstance(result, str):
            image_path = result
        elif isinstance(result, dict):
            image_path = result.get('image_path') or result.get('path') or result.get('url')
            prompt = result.get('prompt') or result.get('description')
        
        # Ensure web-accessible path
        if image_path and not image_path.startswith('/static/'):
            if image_path.startswith('static/'):
                image_path = '/' + image_path
            elif not image_path.startswith('/'):
                image_path = '/static/generated_images/' + image_path
        
        return {
            'image_path': image_path,
            'prompt': prompt,
            'alt_text': prompt or 'Generated image'
        }
    
    def _format_text_content(self, result: Any) -> Dict[str, Any]:
        """Format text result."""
        if isinstance(result, dict):
            # Structured data (like weather)
            return {
                'text': result.get('description') or result.get('summary') or json.dumps(result, indent=2),
                'structured': result
            }
        else:
            return {'text': str(result)}
    
    def _format_list_content(self, result: Any) -> Dict[str, Any]:
        """Format list/search results."""
        items = []
        
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    items.append({
                        'title': item.get('title', 'Result'),
                        'snippet': item.get('snippet') or item.get('description') or str(item)[:200],
                        'url': item.get('url') or item.get('link')
                    })
                else:
                    items.append({
                        'title': 'Result',
                        'snippet': str(item)[:200],
                        'url': None
                    })
        else:
            items = [{
                'title': 'Result',
                'snippet': str(result)[:200],
                'url': None
            }]
        
        return {
            'items': items[:5],  # Limit to 5
            'total': len(items)
        }
    
    def _format_code_content(self, result: Any) -> Dict[str, Any]:
        """Format code/API result."""
        if isinstance(result, dict):
            return {
                'code': json.dumps(result, indent=2),
                'language': 'json',
                'summary': result.get('summary') or result.get('description')
            }
        else:
            return {
                'code': str(result),
                'language': 'text'
            }
    
    def _create_error_spec(self, tool_name: str, error: Any, config: Dict) -> ToolCardSpec:
        """Create error ToolCardSpec."""
        error_msg = str(error) if not isinstance(error, str) else error
        
        return ToolCardSpec(
            card_type=CardType.ERROR,
            header_icon='⚠️',
            header_title=f"{config.get('header_title', tool_name)} - Error",
            content={
                'error': error_msg,
                'friendly_message': "Something went wrong with that request."
            },
            llm_commentary=f"The {tool_name} tool encountered an error: {error_msg[:100]}. Apologize briefly.",
            tool_visible=True,
            inline=True
        )
    
    def _create_timeout_spec(self, tool_name: str, config: Dict) -> ToolCardSpec:
        """Create timeout ToolCardSpec."""
        return ToolCardSpec(
            card_type=CardType.ERROR,
            header_icon='⏱️',
            header_title=f"{config.get('header_title', tool_name)} - Timeout",
            content={
                'error': 'Request timed out',
                'friendly_message': "That took too long to complete.",
                'retryable': True
            },
            llm_commentary="Sorry, that took too long. Want me to try again?",
            tool_visible=True,
            inline=True
        )