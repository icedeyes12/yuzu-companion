"""
Agentic Tool Loop - Enables LLM to react to tool results and retry/fix

Flow:
1. LLM generates tool command
2. Tool executes
3. LLM sees result (in temp context) and decides next action
4. Loop until success, max retries, or LLM decides to stop
5. Save final results to DB
"""

import json
import time
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass
from enum import Enum
from database import Database
from tools.registry import get_tool_role, build_markdown_contract
from tools.orchestration.mcp_manager import get_mcp_manager


class ToolOutcome(Enum):
    SUCCESS = "success"
    ERROR = "error"
    NEEDS_RETRY = "needs_retry"
    MAX_RETRIES = "max_retries"
    GIVE_UP = "give_up"


@dataclass
class ToolAttempt:
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
    Manages iterative tool execution with LLM feedback.
    
    The LLM can see each tool result and decide to:
    - Retry with same parameters
    - Retry with modified parameters
    - Try a different tool
    - Give up and explain the failure
    - Continue with success
    """
    
    def __init__(self, profile: Dict, session_id: int, max_retries: int = 3):
        self.profile = profile
        self.session_id = session_id
        self.max_retries = max_retries
        self.attempts: List[ToolAttempt] = []
        self.mcp_manager = get_mcp_manager()
        
    def execute_with_agentic_loop(
        self,
        initial_command: str,
        command_info: Dict[str, Any],
        generate_ai_response_func: Callable,
        interface: str = "web"
    ) -> Tuple[str, List[ToolAttempt]]:
        """
        Execute tool with agentic retry loop.
        
        Returns:
            (final_response, attempts_history)
        """
        attempt_number = 0
        final_response = None
        
        while attempt_number < self.max_retries:
            attempt_number += 1
            
            # Execute the tool
            attempt = self._execute_tool_attempt(
                attempt_number,
                command_info
            )
            self.attempts.append(attempt)
            
            # Check if success
            if attempt.error is None:
                # Success! Let LLM decide if we need more tools or we're done
                decision = self._ask_llm_for_decision(
                    attempt,
                    generate_ai_response_func,
                    interface,
                    is_success=True
                )
                
                if decision.get("action") == "continue":
                    # LLM is satisfied, generate final response
                    final_response = self._generate_final_response(
                        generate_ai_response_func,
                        interface
                    )
                    return final_response, self.attempts
                    
                elif decision.get("action") == "another_tool":
                    # LLM wants to use another tool
                    command_info = decision.get("new_command_info", command_info)
                    continue
                    
                else:
                    # Default: continue with success
                    final_response = self._generate_final_response(
                        generate_ai_response_func,
                        interface
                    )
                    return final_response, self.attempts
            else:
                # Error! Let LLM decide what to do
                decision = self._ask_llm_for_decision(
                    attempt,
                    generate_ai_response_func,
                    interface,
                    is_success=False
                )
                
                action = decision.get("action", "give_up")
                
                if action == "retry_same":
                    # Retry with same parameters
                    print(f"[AGENTIC] LLM decided to retry (attempt {attempt_number + 1})")
                    continue
                    
                elif action == "retry_modified":
                    # Retry with modified parameters
                    new_args = decision.get("modified_arguments", attempt.arguments)
                    command_info["parsed_args"] = new_args
                    print(f"[AGENTIC] LLM decided to retry with modifications (attempt {attempt_number + 1})")
                    continue
                    
                elif action == "try_alternative":
                    # Try a different tool
                    alt_tool = decision.get("alternative_tool", command_info)
                    command_info = alt_tool
                    print(f"[AGENTIC] LLM decided to try alternative tool (attempt {attempt_number + 1})")
                    continue
                    
                elif action == "give_up":
                    # LLM gives up, explain the failure
                    final_response = self._generate_failure_explanation(
                        attempt,
                        generate_ai_response_func,
                        interface
                    )
                    return final_response, self.attempts
                    
                else:
                    # Unknown action, give up
                    final_response = self._generate_failure_explanation(
                        attempt,
                        generate_ai_response_func,
                        interface
                    )
                    return final_response, self.attempts
        
        # Max retries reached
        final_response = self._generate_max_retries_response(
            generate_ai_response_func,
            interface
        )
        return final_response, self.attempts
    
    def _execute_tool_attempt(
        self,
        attempt_number: int,
        command_info: Dict[str, Any]
    ) -> ToolAttempt:
        """Execute a single tool attempt."""
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
                    # Format as markdown contract
                    output_text = json.dumps(result.get("result", {}), indent=2)
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
        # Use pre-parsed args if available (from retry_modified)
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
            # For MCP fetch, args might be URL or JSON
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
    
    def _ask_llm_for_decision(
        self,
        attempt: ToolAttempt,
        generate_ai_response_func: Callable,
        interface: str,
        is_success: bool
    ) -> Dict[str, Any]:
        """Ask LLM what to do after a tool execution."""
        
        # Build context for LLM
        if is_success:
            prompt = f"""You just executed a tool. Here is the result:

Tool: {attempt.tool_name}
Arguments: {json.dumps(attempt.arguments, indent=2)}
Result: {attempt.result[:500] if attempt.result else "(empty)"}

Based on this result, decide your next action:
- "continue" - The result is good, continue with your response
- "another_tool" - You need to use another tool to complete the task

Respond with ONLY a JSON object in this format:
{{"action": "continue"}} or {{"action": "another_tool", "reason": "why you need another tool"}}
"""
        else:
            # Error case - give LLM options to retry/fix
            prompt = f"""You just executed a tool but it failed. Here is what happened:

Tool: {attempt.tool_name}
Arguments: {json.dumps(attempt.arguments, indent=2)}
Error: {attempt.error}

This is attempt #{attempt.attempt_number} of max {self.max_retries}.

Decide your next action:
- "retry_same" - Retry with the same arguments (maybe transient error)
- "retry_modified" - Retry with modified arguments (explain what to change)
- "try_alternative" - Try a completely different tool/approach
- "give_up" - Can't fix this, explain the failure to user

Respond with ONLY a JSON object:
{{"action": "retry_same"}}
{{"action": "retry_modified", "modified_arguments": {{...}}}}
{{"action": "try_alternative", "alternative_tool": {{"type": "...", "command": "...", "args": "..."}}}}
{{"action": "give_up", "reason": "why you're giving up"}}
"""
        
        # Call LLM for decision
        try:
            response = generate_ai_response_func(
                self.profile,
                prompt,
                interface,
                self.session_id
            )
            
            # Extract JSON from response
            json_match = self._extract_json(response)
            if json_match:
                return json.loads(json_match)
            else:
                # Default to giving up if we can't parse
                return {"action": "give_up", "reason": "Could not parse LLM decision"}
                
        except Exception as e:
            print(f"[AGENTIC] Error asking LLM for decision: {e}")
            return {"action": "give_up", "reason": f"Error: {e}"}
    
    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON object from text."""
        import re
        # Try to find JSON object in text
        match = re.search(r'\{[^{}]*\}', text)
        if match:
            return match.group(0)
        
        # Try with nested braces (simple approach)
        start = text.find('{')
        if start != -1:
            # Count braces to find matching close
            count = 0
            for i, char in enumerate(text[start:]):
                if char == '{':
                    count += 1
                elif char == '}':
                    count -= 1
                    if count == 0:
                        return text[start:start+i+1]
        return None
    
    def _generate_final_response(
        self,
        generate_ai_response_func: Callable,
        interface: str
    ) -> str:
        """Generate final response after successful tool execution."""
        # All attempts are now in the conversation context
        # Generate response based on accumulated results
        return generate_ai_response_func(
            self.profile,
            "",  # Empty prompt - LLM should respond based on context
            interface,
            self.session_id
        )
    
    def _generate_failure_explanation(
        self,
        last_attempt: ToolAttempt,
        generate_ai_response_func: Callable,
        interface: str
    ) -> str:
        """Generate explanation for why tools failed."""
        prompt = f"""You tried {last_attempt.attempt_number} times but the tool keeps failing.

Final error: {last_attempt.error}

Please explain to the user what happened and what you tried. Be honest about the failure."""
        
        return generate_ai_response_func(
            self.profile,
            prompt,
            interface,
            self.session_id
        )
    
    def _generate_max_retries_response(
        self,
        generate_ai_response_func: Callable,
        interface: str
    ) -> str:
        """Generate response when max retries reached."""
        prompt = f"""You reached the maximum number of retries ({self.max_retries}) but could not succeed.

Please explain to the user that you tried multiple approaches but couldn't complete the task."""
        
        return generate_ai_response_func(
            self.profile,
            prompt,
            interface,
            self.session_id
        )


def execute_tool_with_agentic_loop(
    profile: Dict,
    user_message: str,
    command_info: Dict[str, Any],
    session_id: int,
    generate_ai_response_func: Callable,
    interface: str = "web",
    max_retries: int = 3
) -> Tuple[str, str, List[ToolAttempt]]:
    """
    Convenience function to execute tool with agentic loop.
    
    Returns:
        (tool_output_for_display, final_ai_response, attempts_history)
    """
    loop = AgenticToolLoop(profile, session_id, max_retries)
    final_response, attempts = loop.execute_with_agentic_loop(
        user_message,
        command_info,
        generate_ai_response_func,
        interface
    )
    
    # Build combined tool output for display
    tool_outputs = []
    for attempt in attempts:
        if attempt.error:
            tool_outputs.append(f"Attempt {attempt.attempt_number}: ❌ {attempt.error}")
        else:
            preview = attempt.result[:200] + "..." if attempt.result and len(attempt.result) > 200 else attempt.result
            tool_outputs.append(f"Attempt {attempt.attempt_number}: ✅ {preview}")
    
    combined_tool_output = "\n".join(tool_outputs)
    
    return combined_tool_output, final_response, attempts
