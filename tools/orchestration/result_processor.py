"""
ResultProcessor - Transform raw tool output to UI-ready format

Converts tool execution results into structured specifications
for rendering in the chat UI.
"""

import json
import re
from typing import Any, Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

from tools.orchestration.tool_router import ToolResult, ToolType


class CardType(Enum):
    """Types of tool card displays"""
    IMAGE = "image"
    TEXT = "text"
    LIST = "list"
    CODE = "code"
    ERROR = "error"
    MIXED = "mixed"


@dataclass
class ToolCardSpec:
    """
    UI specification for rendering a tool result card.
    
    This is what gets sent to the frontend for rendering.
    """
    card_type: str           # CardType value
    header_icon: str         # Emoji icon for header
    header_title: str        # Tool display name
    content: Any              # Rendered content
    llm_commentary: str       # Optional LLM text to show
    raw_result: Dict          # Raw result for DB storage
    status: str              # 'success' or 'error'
    error_message: Optional[str] = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        return {
            "card_type": self.card_type,
            "header_icon": self.header_icon,
            "header_title": self.header_title,
            "content": self.content,
            "llm_commentary": self.llm_commentary,
            "raw_result": self.raw_result,
            "status": self.status,
            "error_message": self.error_message,
            "metadata": self.metadata
        }


class ResultProcessor:
    """
    Transform raw tool output into UI-ready card specifications.
    
    Handles:
    - Parsing different output formats (JSON, text, markdown)
    - Detecting content types (images, lists, code, errors)
    - Generating appropriate UI components
    - Creating LLM commentary prompts for follow-up
    """
    
    # Tool icons mapping
    TOOL_ICONS = {
        "image_generate": "🖼️",
        "request": "🌐",
        "memory_search": "🔍",
        "memory_sql": "🗄️",
        "image_analyze": "👁️",
        "web_search": "🔎",
        "weather": "🌤️",
    }
    
    # Tool display names
    TOOL_DISPLAY_NAMES = {
        "image_generate": "Image Generation",
        "request": "Web Request",
        "memory_search": "Memory Search",
        "memory_sql": "Database Query",
        "image_analyze": "Image Analysis",
        "web_search": "Web Search",
        "weather": "Weather",
    }
    
    def process(self, tool_result: ToolResult) -> ToolCardSpec:
        """
        Process a ToolResult into a ToolCardSpec for UI rendering.
        
        Args:
            tool_result: The result from ToolRouter execution
        
        Returns:
            ToolCardSpec ready for UI rendering
        """
        tool_name = tool_result.tool_name
        tool_type = tool_result.tool_type
        
        # Get icon and display name
        header_icon = self.TOOL_ICONS.get(tool_name, "🔧")
        header_title = self.TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        
        if not tool_result.success:
            return ToolCardSpec(
                card_type=CardType.ERROR.value,
                header_icon=header_icon,
                header_title=header_title,
                content=None,
                llm_commentary="",
                raw_result=tool_result.to_dict(),
                status="error",
                error_message=tool_result.error,
                metadata=tool_result.metadata
            )
        
        # Process successful result based on tool type
        if tool_type == ToolType.INTERNAL:
            return self._process_internal_result(tool_result)
        elif tool_type == ToolType.MCP_STDIO:
            return self._process_mcp_result(tool_result)
        elif tool_type == ToolType.MCP_HTTP:
            return self._process_mcp_result(tool_result)
        else:
            return self._process_generic_result(tool_result)
    
    def _process_internal_result(self, tool_result: ToolResult) -> ToolCardSpec:
        """Process result from internal tool"""
        
        tool_name = tool_result.tool_name
        output = tool_result.output
        header_icon = self.TOOL_ICONS.get(tool_name, "🔧")
        header_title = self.TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        
        # Handle different internal tools
        if tool_name == "image_generate":
            return self._process_image_result(output, header_icon, header_title)
        elif tool_name == "request":
            return self._process_request_result(output, header_icon, header_title)
        elif tool_name in ("memory_search", "memory_sql"):
            return self._process_memory_result(output, header_icon, header_title)
        elif tool_name == "image_analyze":
            return self._process_image_analyze_result(output, header_icon, header_title)
        else:
            return self._process_generic_result(tool_result)
    
    def _process_image_result(self, output: Any, icon: str, title: str) -> ToolCardSpec:
        """Process image generation result"""
        
        # Try to extract image path from output
        image_path = None
        
        if isinstance(output, str):
            # Look for JSON with image_path
            try:
                # Try to find JSON in output
                json_match = re.search(r'\{[^{}]*"image_path"[^{}]*\}', output)
                if json_match:
                    data = json.loads(json_match.group())
                    image_path = data.get("image_path")
            except:
                pass
            
            # Try to find image URL/path in text
            if not image_path:
                url_match = re.search(r'(https?://[^\s]+\.(?:png|jpg|jpeg|gif|webp))', output)
                if url_match:
                    image_path = url_match.group(1)
        
        # Determine card content
        if image_path:
            content = {
                "type": "image",
                "path": image_path,
                "alt": "Generated image"
            }
        else:
            content = {
                "type": "text",
                "text": str(output)[:500]
            }
        
        return ToolCardSpec(
            card_type=CardType.IMAGE.value,
            header_icon=icon,
            header_title=title,
            content=content,
            llm_commentary="",
            raw_result={"image_path": image_path} if image_path else {},
            status="success"
        )
    
    def _process_request_result(self, output: Any, icon: str, title: str) -> ToolCardSpec:
        """Process web request result"""
        
        card_type = CardType.TEXT.value
        content_text = ""
        
        if isinstance(output, str):
            # Try to parse as JSON
            try:
                data = json.loads(output)
                # Format JSON nicely
                content_text = json.dumps(data, indent=2)[:2000]
                
                # Detect if it's a list
                if isinstance(data, list):
                    card_type = CardType.LIST.value
                    content = [{"text": json.dumps(item, indent=2)[:500]} for item in data[:10]]
                elif isinstance(data, dict):
                    # Check for common API response patterns
                    if "results" in data:
                        card_type = CardType.LIST.value
                        content = data["results"][:10]
                    elif "data" in data:
                        content = data["data"]
                    else:
                        content = {"text": content_text}
                else:
                    content = {"text": content_text}
                    
            except json.JSONDecodeError:
                # Plain text
                content = {"text": output[:2000]}
        
        elif isinstance(output, dict):
            content_text = json.dumps(output, indent=2)[:2000]
            content = {"text": content_text}
        elif isinstance(output, list):
            content = [{"text": json.dumps(item, indent=2)[:500]} for item in output[:10]]
            card_type = CardType.LIST.value
        else:
            content = {"text": str(output)[:2000]}
        
        return ToolCardSpec(
            card_type=card_type,
            header_icon=icon,
            header_title=title,
            content=content,
            llm_commentary="",
            raw_result={"output": str(output)[:5000]},
            status="success"
        )
    
    def _process_memory_result(self, output: Any, icon: str, title: str) -> ToolCardSpec:
        """Process memory search/SQL result"""
        
        card_type = CardType.TEXT.value
        content = {}
        
        if isinstance(output, str):
            # Parse markdown details block if present
            # Extract content from <details> block
            details_match = re.search(r'<details>.*?</details>', output, re.DOTALL)
            if details_match:
                # Extract text content
                text_content = re.sub(r'<[^>]+>', '', details_match.group())
                content = {"text": text_content.strip()[:2000]}
            else:
                content = {"text": output[:2000]}
        
        elif isinstance(output, dict):
            content = output
        elif isinstance(output, list):
            card_type = CardType.LIST.value
            content = {"items": output[:20]}
        
        return ToolCardSpec(
            card_type=card_type,
            header_icon=icon,
            header_title=title,
            content=content,
            llm_commentary="",
            raw_result={"result": str(output)[:5000]},
            status="success"
        )
    
    def _process_image_analyze_result(self, output: Any, icon: str, title: str) -> ToolCardSpec:
        """Process image analysis result"""
        
        content = {}
        
        if isinstance(output, str):
            content = {"text": output[:2000]}
        elif isinstance(output, dict):
            # Look for description field
            description = output.get("description") or output.get("text") or output.get("analysis")
            if description:
                content = {"text": description[:2000]}
            else:
                content = output
        else:
            content = {"text": str(output)[:2000]}
        
        return ToolCardSpec(
            card_type=CardType.TEXT.value,
            header_icon=icon,
            header_title=title,
            content=content,
            llm_commentary="",
            raw_result={"analysis": str(output)[:5000]},
            status="success"
        )
    
    def _process_mcp_result(self, tool_result: ToolResult) -> ToolCardSpec:
        """Process result from MCP tool"""
        
        tool_name = tool_result.tool_name
        output = tool_result.output
        header_icon = self.TOOL_ICONS.get(tool_name, "📦")
        header_title = f"MCP: {self.TOOL_DISPLAY_NAMES.get(tool_name, tool_name)}"
        
        # MCP results typically come as structured data
        content = {}
        
        if isinstance(output, dict):
            # MCP results often have 'content' or 'text' field
            if "content" in output:
                content = output["content"]
            elif "text" in output:
                content = {"text": output["text"]}
            else:
                content = output
        elif isinstance(output, str):
            content = {"text": output[:2000]}
        else:
            content = {"data": str(output)[:2000]}
        
        return ToolCardSpec(
            card_type=CardType.MIXED.value,
            header_icon=header_icon,
            header_title=header_title,
            content=content,
            llm_commentary="",
            raw_result=tool_result.to_dict(),
            status="success",
            metadata=tool_result.metadata
        )
    
    def _process_generic_result(self, tool_result: ToolResult) -> ToolCardSpec:
        """Process any other tool result"""
        
        tool_name = tool_result.tool_name
        output = tool_result.output
        header_icon = self.TOOL_ICONS.get(tool_name, "🔧")
        header_title = self.TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        
        content = {}
        
        if isinstance(output, str):
            # Check for JSON
            try:
                data = json.loads(output)
                content = {"text": json.dumps(data, indent=2)[:2000]}
            except:
                content = {"text": output[:2000]}
        elif isinstance(output, (dict, list)):
            content = {"data": output}
        else:
            content = {"text": str(output)[:2000]}
        
        return ToolCardSpec(
            card_type=CardType.TEXT.value,
            header_icon=header_icon,
            header_title=header_title,
            content=content,
            llm_commentary="",
            raw_result={"output": str(output)[:5000]},
            status="success"
        )
    
    def create_llm_commentary_prompt(self, tool_result: ToolResult, card_spec: ToolCardSpec) -> str:
        """
        Create a prompt for the LLM to generate natural commentary about the tool result.
        
        This is used for the optional second pass when the user wants
        the AI to respond to the tool result.
        """
        tool_name = tool_result.tool_name
        
        # Build context based on tool type
        if tool_name == "image_generate":
            return f"""The user requested an image generation. 
A new image has been created based on their prompt.
Respond naturally - acknowledge the creation without being overly enthusiastic.
Keep it brief (1-2 sentences)."""
        
        elif tool_name == "request":
            return f"""A web request was made and returned results.
Summarize the key findings for the user in natural language.
Be concise and informative."""
        
        elif tool_name in ("memory_search", "memory_sql"):
            return f"""A memory/database query was performed.
Present the results to the user in a helpful way.
If there are multiple results, summarize them."""
        
        elif tool_name == "image_analyze":
            return f"""An image was analyzed.
Present the description to the user in a natural way."""
        
        else:
            return f"""A tool ({tool_name}) was executed.
Respond naturally to the user about the result."""


# Singleton instance
_result_processor = None

def get_result_processor() -> ResultProcessor:
    """Get or create ResultProcessor singleton"""
    global _result_processor
    if _result_processor is None:
        _result_processor = ResultProcessor()
    return _result_processor
