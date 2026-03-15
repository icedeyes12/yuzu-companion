"""Message normalization utilities.

Centralizes message handling across all providers.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class MessageAnalysis:
    """Analysis result for a message."""
    has_images: bool
    image_urls: List[str]
    is_code: bool
    is_tool_command: bool
    tool_name: Optional[str]
    tool_args: Optional[str]


class MessageNormalizer:
    """Centralized message normalization."""
    
    # Patterns for image detection
    MARKDOWN_IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    URL_PATTERN = re.compile(r'https?://[^\s<>"\'{}]+')
    
    # Image hosting domains
    IMAGE_DOMAINS = [
        'ibb.co', 'imgur.com', 'gyazo.com', 'prntscr.com', 'prnt.sc',
        'tinypic.com', 'postimg.org', 'imageshack.us', 'flickr.com',
        'deviantart.com', 'artstation.com', 'cdn.discordapp.com',
        'media.discordapp.net', 'i.redd.it', 'i.imgur.com'
    ]
    
    # Code detection patterns
    CODE_INDICATORS = [
        'import ', 'from ', 'def ', 'class ', 'if __name__',
        '```', '    ', '\t', '// ', '# ', '/*', '*/'
    ]
    
    # Tool command patterns
    TOOL_COMMANDS = {
        'imagine': 'image_generate',
        'image_generate': 'image_generate',
        'request': 'request',
        'fetch': 'request',
        'memory_search': 'memory_search',
        'memory_sql': 'memory_sql',
    }
    
    def analyze(self, message: str) -> MessageAnalysis:
        """Analyze a message for images, code, and tool commands."""
        image_urls = self._extract_image_urls(message)
        
        # Check for tool commands
        tool_name, tool_args = self._extract_tool_command(message)
        
        return MessageAnalysis(
            has_images=len(image_urls) > 0,
            image_urls=image_urls,
            is_code=self._looks_like_code(message),
            is_tool_command=tool_name is not None,
            tool_name=tool_name,
            tool_args=tool_args,
        )
    
    def normalize_for_provider(
        self,
        messages: List[Dict[str, Any]],
        provider_name: str
    ) -> List[Dict[str, Any]]:
        """Normalize messages for a specific provider.
        
        Different providers have different requirements:
        - Chutes: Only one system message allowed (must be first)
        - Cerebras: Standard roles only
        - OpenRouter: Flexible
        """
        normalized = []
        
        if provider_name == 'chutes':
            # Chutes requires single system message at beginning
            normalized = self._normalize_for_chutes(messages)
        else:
            # Standard normalization for other providers
            normalized = self._normalize_standard(messages)
        
        return normalized
    
    def _normalize_standard(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Standard normalization: tool roles -> assistant."""
        standard_roles = {'system', 'user', 'assistant', 'tool'}
        normalized = []
        
        for msg in messages:
            role = msg.get('role', '')
            
            if role not in standard_roles:
                # Tool role - convert to assistant
                normalized.append({
                    'role': 'assistant',
                    'content': f"[{role}]\n{msg.get('content', '')}"
                })
            else:
                normalized.append(msg)
        
        return normalized
    
    def _normalize_for_chutes(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Chutes-specific normalization: single system message."""
        system_contents = []
        normalized = []
        
        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            
            if role == 'system':
                system_contents.append(content)
            elif role not in {'user', 'assistant', 'tool'}:
                # Tool role - convert to assistant
                normalized.append({
                    'role': 'assistant',
                    'content': f"[{role}]\n{content}"
                })
            else:
                normalized.append(msg)
        
        # Merge all system messages into one at the beginning
        if system_contents:
            merged_system = '\n\n'.join(system_contents)
            return [{'role': 'system', 'content': merged_system}] + normalized
        
        return normalized
    
    def _extract_image_urls(self, text: str) -> List[str]:
        """Extract image URLs from text."""
        urls = []
        
        # Extract markdown images
        for match in self.MARKDOWN_IMAGE_PATTERN.finditer(text):
            alt, url = match.groups()
            urls.append(url)
        
        # Extract direct image URLs
        for match in self.URL_PATTERN.finditer(text):
            url = match.group()
            
            # Skip if in code context
            if self._is_url_in_code_context(text, url):
                continue
            
            # Check if it's an image URL
            if self._is_image_url(url):
                urls.append(url)
        
        return urls
    
    def _is_image_url(self, url: str) -> bool:
        """Check if URL is likely an image."""
        # Check image domains
        if any(domain in url.lower() for domain in self.IMAGE_DOMAINS):
            return True
        
        # Check image extensions
        image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        return any(url.lower().endswith(ext) or f"{ext}?" in url.lower() for ext in image_exts)
    
    def _looks_like_code(self, text: str) -> bool:
        """Check if text looks like code."""
        return any(indicator in text for indicator in self.CODE_INDICATORS)
    
    def _is_url_in_code_context(self, text: str, url: str) -> bool:
        """Check if URL appears in code context."""
        url_pos = text.find(url)
        if url_pos == -1:
            return False
        
        # Get context around URL
        before = text[max(0, url_pos-20):url_pos]
        after = text[url_pos+len(url):min(len(text), url_pos+len(url)+20)]
        
        # Code indicators
        indicators = ['import ', 'from ', 'def ', 'class ', '//', '#', '"""', "'''", '/*']
        
        for ind in indicators:
            if ind in before or ind in after:
                return True
        
        # Odd quote count suggests code
        quotes = before.count('"') + before.count("'") + after.count('"') + after.count("'")
        if quotes % 2 == 1:
            return True
        
        return False
    
    def _extract_tool_command(self, message: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract tool command from message.
        
        Returns: (tool_name, tool_args) or (None, None)
        """
        message = message.strip()
        
        # Check for /command syntax
        if message.startswith('/'):
            parts = message.split(None, 1)
            cmd = parts[0][1:]  # Remove leading /
            args = parts[1] if len(parts) > 1 else ""
            
            if cmd in self.TOOL_COMMANDS:
                return self.TOOL_COMMANDS[cmd], args
        
        # Check for natural language patterns
        msg_lower = message.lower()
        
        # Image generation patterns
        if any(p in msg_lower for p in ['generate an image', 'create an image', 'draw ', 'imagine ']):
            # Extract prompt
            for trigger in ['generate an image of ', 'create an image of ', 'draw me ', 'imagine ']:
                if trigger in msg_lower:
                    prompt = message[msg_lower.find(trigger) + len(trigger):]
                    return 'image_generate', prompt.strip()
        
        return None, None
    
    def remove_image_markdown(self, text: str) -> str:
        """Remove image markdown and replace with placeholder."""
        def replace(match):
            alt = match.group(1)
            if alt and alt not in ['Uploaded Image', 'Generated Image']:
                return f" [Image: {alt}] "
            return " [Image] "
        
        clean = self.MARKDOWN_IMAGE_PATTERN.sub(replace, text)
        clean = re.sub(r'\n\s*\n', '\n\n', clean)
        return clean.strip()


# Singleton instance
_normalizer = None


def get_normalizer() -> MessageNormalizer:
    """Get or create normalizer singleton."""
    global _normalizer
    if _normalizer is None:
        _normalizer = MessageNormalizer()
    return _normalizer
