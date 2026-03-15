"""
Agentic Tool Loop - Simplified single-pass execution

Flow:
1. LLM generates tool command
2. Tool executes once
3. Tool output shown as card
4. LLM generates final response based on context

No retry loop - keeps it simple and predictable.
"""

import json
import time
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass
from tools.orchestration.mcp_manager import get_mcp_manager


@dataclass
class ToolAttempt:
    """Record of a single tool execution attempt."""
    attempt_number: int
    tool_type: str  # "internal" or "mcp"
    tool_name: str
    server_name: Optional[str]  # For MCP tools
    arguments: Dict[str, Any]
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt": self.attempt_number,
            "tool": f"{self.tool_type}:{self.server_name}:{self.tool_name}" if self.server_name else f"{self.tool_type}:{self.tool_name}",
            "arguments": self.arguments,
            "result_preview": (self.result[:200] + "...") if self.result and len(self.result) > 200 else self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class AgenticToolLoop:
    """
    Simplified tool execution - single pass, no retry loop.
    
    Why simple?
    - User sees exactly what happened
    - LLM responds naturally to results
    - No confusing "Attempt 1: ✅" messages
    - Easy to debug and understand
    """
    
    def __init__(self, profile: Dict, session_id: int, max_retries: int = 1):
        self.profile = profile
        self.session_id = session_id
        self.max_retries = max_retries  # Kept for API compatibility but ignored
        self.attempts: List[ToolAttempt] = []
        self.mcp_manager = get_mcp_manager()
        
    def execute(
        self,
        initial_command: str,
        command_info: Dict[str, Any],
        generate_ai_response_func: Callable,
        interface: str = "web"
    ) -> Tuple[str, List[ToolAttempt]]:
        """
        Simplified single-pass tool execution.
        
        Executes tool once and generates final response.
        No retry loop - simple and predictable.
        
        Returns:
            (final_response, attempts_list)
        """
        # Execute the tool
        attempt = self._execute_tool_attempt(1, command_info)
        self.attempts.append(attempt)
        
        # Build display output for user
        if attempt.error:
            display_output = f"Error: {attempt.error}"
        else:
            display_output = attempt.result or "(no output)"
        
        # Generate final response with tool result in context
        final_response = self._generate_final_response(
            generate_ai_response_func,
            interface
        )
        
        return final_response, self.attempts

    def _execute_tool_attempt(
        self,
        attempt_number: int,
        command_info: Dict[str, Any]
    ) -> ToolAttempt:
        """
        Execute tool once and return the attempt result.
        
        Simple, predictable, no magic.
        
        Returns:
            ToolAttempt with result or error
        """
        start_time = time.time()
        
        tool_type = command_info.get("type", "internal")
        tool_name = command_info.get("command", "")
        server_name = command_info.get("server")  # For MCP
        
        # Parse arguments
        args_str = command_info.get("args", "")
        arguments = self._parse_arguments(tool_name, args_str, command_info)
        
        try:
            if tool_type == "mcp" and server_name:
                # MCP tool execution
                result = self.mcp_manager.call_tool(
                    server_name,
                    tool_name,
                    arguments
                )
                
                duration_ms = (time.time() - start_time) * 1000
                
                if result.get("success"):
                    raw_result = result.get("result", {})
                    output_text = self._extract_mcp_output(raw_result)
                    return ToolAttempt(
                        attempt_number=attempt_number,
                        tool_type="mcp",
                        tool_name=tool_name,
                        server_name=server_name,
                        arguments=arguments,
                        result=output_text,
                        duration_ms=duration_ms
                    )
                else:
                    return ToolAttempt(
                        attempt_number=attempt_number,
                        tool_type="mcp",
                        tool_name=tool_name,
                        server_name=server_name,
                        arguments=arguments,
                        error=result.get("error", "Unknown error"),
                        duration_ms=duration_ms
                    )
            else:
                # Internal tool execution
                from tools.registry import execute_tool
                result = execute_tool(tool_name, arguments, session_id=self.session_id)
                
                duration_ms = (time.time() - start_time) * 1000
                
                # Check if result contains error
                if "Error:" in result or "error" in result.lower():
                    return ToolAttempt(
                        attempt_number=attempt_number,
                        tool_type="internal",
                        tool_name=tool_name,
                        server_name=None,
                        arguments=arguments,
                        error=result,
                        duration_ms=duration_ms
                    )
                else:
                    return ToolAttempt(
                        attempt_number=attempt_number,
                        tool_type="internal",
                        tool_name=tool_name,
                        server_name=None,
                        arguments=arguments,
                        result=result,
                        duration_ms=duration_ms
                    )
                    
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return ToolAttempt(
                attempt_number=attempt_number,
                tool_type=tool_type,
                tool_name=tool_name,
                server_name=server_name,
                arguments=arguments,
                error=str(e),
                duration_ms=duration_ms
            )
    
    def _parse_arguments(
        self,
        tool_name: str,
        args_str: str,
        command_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse tool arguments from command string."""
        # Use pre-parsed args if available
        if "parsed_args" in command_info:
            return command_info["parsed_args"]
        
        # Parse based on tool type
        if tool_name == "imagine":
            return {"prompt": args_str}
        elif tool_name == "request":
            return {"url": args_str}
        elif tool_name in ("memory_search", "memory_sql"):
            try:
                return json.loads(args_str) if args_str else {"query": ""}
            except:
                return {"query": args_str}
        elif tool_name == "execute_command":
            return {"command": args_str}
        elif tool_name == "fetch":
            try:
                parsed = json.loads(args_str)
                if "url" in parsed:
                    return parsed
                return {"url": args_str}
            except:
                return {"url": args_str}
        else:
            # Try JSON parse, fallback to query string
            try:
                return json.loads(args_str) if args_str else {}
            except:
                return {"query": args_str}
    
    def _extract_mcp_output(self, result: Dict) -> str:
        """Extract readable text from MCP tool result."""
        if not result:
            return "(no output)"
        
        # Handle content array format: {"content": [{"type": "text", "text": "..."}]}
        content = result.get("content")
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text" and "text" in item:
                        texts.append(item["text"])
                    elif "data" in item:  # For images/audio
                        texts.append(f"[{item.get('type', 'blob')}: {len(item['data'])} bytes]")
            return "\n".join(texts) if texts else json.dumps(result, indent=2)
        
        # Handle structuredContent format: {"structuredContent": {"content": "..."}}
        structured = result.get("structuredContent")
        if isinstance(structured, dict) and "content" in structured:
            return structured["content"]
        
        # Fallback: return the whole thing as JSON
        return json.dumps(result, indent=2)

    def _generate_final_response(
        self,
        generate_ai_response_func: Callable,
        interface: str
    ) -> str:
        """Generate final response after tool execution."""
        # Tool results are now in DB context
        # LLM responds naturally based on conversation history
        return generate_ai_response_func(
            self.profile,
            "",  # Empty prompt - respond based on context
            interface,
            self.session_id
        )


# Legacy compatibility - redirect to simpler implementation
def execute_tool_with_agentic_loop(
    profile: Dict,
    user_message: str,
    command_info: Dict[str, Any],
    session_id: int,
    generate_ai_response_func: Callable,
    interface: str = "web",
    max_retries: int = 1
) -> Tuple[str, str, List[ToolAttempt]]:
    """
    Execute tool (legacy compatibility).
    
    Now just executes once - no retry loop.
    
    Returns:
        (tool_output_for_display, final_ai_response, attempts_history)
    """
    loop = AgenticToolLoop(profile, session_id, max_retries)
    attempt = loop.execute(command_info)
    
    # Build simple display output (no "Attempt X:" prefix)
    if attempt.error:
        display_output = f"❌ Error: {attempt.error}"
    else:
        display_output = attempt.result
    
    # Generate final response with tool context already in DB
    final_response = generate_ai_response_func(
        profile,
        "",  # Empty prompt - LLM responds based on context
        interface,
        session_id
    )
    
    return display_output, final_response, [attempt]
