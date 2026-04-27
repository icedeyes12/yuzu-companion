# FILE: app/orchestrator_agentic.py
# DESCRIPTION: Agentic Plan-Execute-Observe loop orchestrator
#              Extends single-pass flow with multi-turn tool calling
#
# Architecture:
#   1. PLAN:    Parse LLM response for commands and thoughts
#   2. EXECUTE: Dispatch tools (local or MCP)
#   3. OBSERVE: Feed tool result back to LLM
#   4. REPEAT:  Until LLM produces final response or max iterations
#
# Safety:
#   - Max iterations: 50 (configurable via AgentConfig)
#   - Total timeout: 30 minutes
#   - Graceful degradation if MCP unavailable

from __future__ import annotations

import time
import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

from app.agents import (
    AgentConfig,
    get_agent_config,
    ToolCall,
    ThoughtBlock,
    parse_command,
    parse_thought,
    strip_command,
)
from app.agents.stream_parser import AgenticStreamParser
from app.dispatch import get_dispatcher
from app.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class TurnResult:
    """Result of a single agentic turn."""
    response_text: str
    tool_calls: list[ToolCall]
    thoughts: list[ThoughtBlock]
    tool_results: list[dict[str, Any]]
    iterations: int
    elapsed_seconds: float


class AgenticOrchestrator:
    """Orchestrator with Plan-Execute-Observe loop.
    
    Usage:
        orchestrator = AgenticOrchestrator()
        result = await orchestrator.run(user_message, session_id)
    """
    
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or get_agent_config()
        self.dispatcher = get_dispatcher()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize dispatcher and discover tools."""
        if self._initialized:
            return
        await self.dispatcher.initialize()
        self._initialized = True
        log.info(
            f"[agentic] Initialized | max_iter={self.config.max_iterations} | "
            f"timeout={self.config.total_timeout_seconds}s | "
            f"mcp={len(self.dispatcher._mcp_tools) > 0}"
        )
    
    async def run(
        self,
        user_message: str,
        session_id: int,
        interface: str = "terminal",
    ) -> TurnResult:
        """Execute the Plan-Execute-Observe loop.
        
        Returns the final response after all tool calls complete.
        """
        start_time = time.time()
        iterations = 0
        all_tool_calls: list[ToolCall] = []
        all_thoughts: list[ThoughtBlock] = []
        all_tool_results: list[dict[str, Any]] = []
        
        # Ensure initialized
        if not self._initialized:
            await self.initialize()
        
        # Get initial LLM response
        current_text = await self._get_llm_response(
            user_message, session_id, interface, iteration=0
        )
        
        # Main loop
        while iterations < self.config.max_iterations:
            elapsed = time.time() - start_time
            if elapsed > self.config.total_timeout_seconds:
                log.warning(f"[agentic] Timeout after {elapsed:.1f}s")
                current_text += "\n\n*[Timeout reached. Here's what I have so far.]*"
                break
            
            # Parse thoughts and commands
            thought = parse_thought(current_text)
            if thought:
                all_thoughts.append(thought)
                if thought.tools_mentioned:
                    log.info(f"[agentic] Thought mentions tools: {thought.tools_mentioned}")
            
            # Check for command
            command = parse_command(current_text)
            if not command:
                # No more commands → final response
                log.info(f"[agentic] No command detected, ending loop at iteration {iterations}")
                break
            
            # Track tool call
            tool_call = ToolCall(
                tool_name=command.tool_name,
                arguments=command.arguments,
                id=f"call_{iterations}",
            )
            all_tool_calls.append(tool_call)
            iterations += 1
            
            log.info(
                f"[agentic] Iteration {iterations}: {command.tool_name}({command.arguments})"
            )
            
            # Execute tool
            result = await self.dispatcher.dispatch(
                command.tool_name,
                command.arguments,
                session_id=session_id,
            )
            all_tool_results.append(result)
            
            if result.get("ok"):
                log.info(f"[agentic] Tool success: {command.tool_name}")
            else:
                log.warning(f"[agentic] Tool error: {result.get('error')}")
            
            # Check if tool is terminal (skip synthesis)
            if self.dispatcher.is_terminal_tool(command.tool_name) and result.get("ok"):
                # Terminal tool with success → return tool result directly
                log.info("[agentic] Terminal tool, returning result")
                current_text = result.get("markdown", "")
                break
            
            # Strip command from response and get synthesis
            clean_text = strip_command(current_text)
            
            # Build synthesis prompt with tool result
            synthesis_prompt = self._build_synthesis_prompt(
                clean_text,
                command.tool_name,
                result,
            )
            
            # Get next LLM response with tool result injected
            current_text = await self._get_llm_response(
                synthesis_prompt,
                session_id,
                interface,
                iteration=iterations,
                tool_result=result,
            )
        
        elapsed = time.time() - start_time
        log.info(
            f"[agentic] Complete | iterations={iterations} | "
            f"tools={len(all_tool_calls)} | elapsed={elapsed:.1f}s"
        )
        
        return TurnResult(
            response_text=current_text,
            tool_calls=all_tool_calls,
            thoughts=all_thoughts,
            tool_results=all_tool_results,
            iterations=iterations,
            elapsed_seconds=elapsed,
        )
    
    async def run_streaming(
        self,
        user_message: str,
        session_id: int,
        interface: str = "web",
        base64_images: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute the loop and yield structured SSE events.
        
        Uses AgenticStreamParser to handle commands split across chunks.
        
        Yields dicts with 'type' and 'data' keys:
          {"type": "thought", "data": {"content": "..."}}
          {"type": "command", "data": {"tool": "...", "args": {...}}}
          {"type": "tool_result", "data": {"ok": true, "output": "..."}}
          {"type": "text", "data": {"chunk": "..."}}
          {"type": "done", "data": {"iterations": 3, "elapsed": 12.5}}
        """
        start_time = time.time()
        iterations = 0
        all_tool_results: list[dict[str, Any]] = []
        
        if not self._initialized:
            await self.initialize()
        
        # Stream initial LLM response with parser
        parser = AgenticStreamParser()
        current_text = ""
        
        async for chunk in self._stream_llm(user_message, session_id, interface, 0, base64_images):
            for safe_chunk, meta in parser.feed(chunk):
                current_text += safe_chunk
                
                if meta.thought:
                    yield {
                        "type": "thought",
                        "data": {
                            "content": meta.thought.content,
                            "planning": meta.thought.planning,
                            "tools": meta.thought.tools_mentioned,
                        },
                    }
                
                if meta.command:
                    yield {
                        "type": "command",
                        "data": {
                            "tool": meta.command.tool_name,
                            "args": meta.command.arguments,
                            "iteration": iterations + 1,
                        },
                    }
                    iterations += 1
                    
                    # Execute tool immediately
                    result = await self.dispatcher.dispatch(
                        meta.command.tool_name,
                        meta.command.arguments,
                        session_id=session_id,
                    )
                    all_tool_results.append(result)
                    
                    yield {
                        "type": "tool_result",
                        "data": {
                            "ok": result.get("ok", False),
                            "output": result.get("markdown", result.get("error", "")),
                        },
                    }
                    
                    # Check if tool is terminal
                    if self.dispatcher.is_terminal_tool(meta.command.tool_name) and result.get("ok"):
                        # Terminal tool success, end here
                        elapsed = time.time() - start_time
                        yield {
                            "type": "done",
                            "data": {
                                "iterations": iterations,
                                "elapsed": round(elapsed, 2),
                                "tools_used": iterations,
                            },
                        }
                        return
                
                # Yield safe text chunk
                if safe_chunk:
                    yield {"type": "text", "data": {"chunk": safe_chunk}}
        
        # Final flush
        for safe_chunk, meta in parser.flush():
            current_text += safe_chunk
            
            if meta.thought:
                yield {
                    "type": "thought",
                    "data": {
                        "content": meta.thought.content,
                        "planning": meta.thought.planning,
                        "tools": meta.thought.tools_mentioned,
                    },
                }
            
            if meta.command:
                yield {
                    "type": "command",
                    "data": {
                        "tool": meta.command.tool_name,
                        "args": meta.command.arguments,
                        "iteration": iterations + 1,
                    },
                }
                iterations += 1
                
                result = await self.dispatcher.dispatch(
                    meta.command.tool_name,
                    meta.command.arguments,
                    session_id=session_id,
                )
                all_tool_results.append(result)
                
                yield {
                    "type": "tool_result",
                    "data": {
                        "ok": result.get("ok", False),
                        "output": result.get("markdown", result.get("error", "")),
                    },
                }
                
                if self.dispatcher.is_terminal_tool(meta.command.tool_name) and result.get("ok"):
                    elapsed = time.time() - start_time
                    yield {
                        "type": "done",
                        "data": {
                            "iterations": iterations,
                            "elapsed": round(elapsed, 2),
                            "tools_used": iterations,
                        },
                    }
                    return
            
            if safe_chunk:
                yield {"type": "text", "data": {"chunk": safe_chunk}}
        
        # Check for more commands (fallback to old parser for compatibility)
        command = parse_command(current_text)
        while command and iterations < self.config.max_iterations:
            elapsed = time.time() - start_time
            if elapsed > self.config.total_timeout_seconds:
                yield {"type": "timeout", "data": {"elapsed": elapsed}}
                break
            
            yield {
                "type": "command",
                "data": {
                    "tool": command.tool_name,
                    "args": command.arguments,
                    "iteration": iterations + 1,
                },
            }
            iterations += 1
            
            result = await self.dispatcher.dispatch(
                command.tool_name,
                command.arguments,
                session_id=session_id,
            )
            all_tool_results.append(result)
            
            yield {
                "type": "tool_result",
                "data": {
                    "ok": result.get("ok", False),
                    "output": result.get("markdown", result.get("error", "")),
                },
            }
            
            if self.dispatcher.is_terminal_tool(command.tool_name) and result.get("ok"):
                break
            
            # Get synthesis
            clean_text = strip_command(current_text)
            synthesis_prompt = self._build_synthesis_prompt(
                clean_text, command.tool_name, result
            )
            
            # Stream synthesis
            parser = AgenticStreamParser()
            current_text = ""
            async for chunk in self._stream_llm(
                synthesis_prompt, session_id, interface, iterations
            ):
                for safe_chunk, meta in parser.feed(chunk):
                    current_text += safe_chunk
                    
                    if safe_chunk:
                        yield {"type": "text", "data": {"chunk": safe_chunk}}
            
            for safe_chunk, meta in parser.flush():
                current_text += safe_chunk
                if safe_chunk:
                    yield {"type": "text", "data": {"chunk": safe_chunk}}
            
            command = parse_command(current_text)
        
        elapsed = time.time() - start_time
        yield {
            "type": "done",
            "data": {
                "iterations": iterations,
                "elapsed": round(elapsed, 2),
                "tools_used": len(all_tool_results),
            },
        }
    
    async def _stream_llm(
        self,
        message: str,
        session_id: int,
        interface: str,
        iteration: int,
        base64_images: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """Stream LLM response chunks.
        
        Uses queue.SimpleQueue for thread-safe communication between
        sync generator (generate_ai_response_streaming) and async iterator.
        """
        import queue
        import threading
        from app.llm_client import generate_ai_response_streaming
        from app.database import Database
        
        profile = Database.get_profile()
        chunk_queue: queue.SimpleQueue[str | None] = queue.SimpleQueue()
        
        # Convert base64 data URLs to vision format for first iteration
        image_content = None
        if base64_images and iteration == 0:
            image_content = [
                {"type": "image_url", "image_url": {"url": url}}
                for url in base64_images
            ]
        
        def _collect_chunks():
            try:
                for chunk in generate_ai_response_streaming(
                    profile, message, interface, session_id,
                    image_content_for_context=image_content,
                ):
                    chunk_queue.put(chunk)
            finally:
                chunk_queue.put(None)
        
        thread = threading.Thread(target=_collect_chunks, daemon=True)
        thread.start()
        
        while True:
            chunk = await asyncio.get_event_loop().run_in_executor(
                None, chunk_queue.get
            )
            if chunk is None:
                break
            yield chunk
        
        thread.join(timeout=1.0)
    
    async def _get_llm_response(
        self,
        message: str,
        session_id: int,
        interface: str,
        iteration: int,
        tool_result: dict[str, Any] | None = None,
    ) -> str:
        """Get LLM response, optionally with tool result injected.
        
        Calls generate_ai_response() directly to avoid recursive
        command execution through handle_user_message().
        """
        from app.llm_client import generate_ai_response
        from app.database import Database
        
        profile = Database.get_profile()
        
        # If we have a tool result, prepend it to the message
        if tool_result:
            tool_markdown = tool_result.get("markdown", str(tool_result))
            message = f"{message}\n\nTool result:\n{tool_markdown}"
        
        response, _ = await asyncio.get_event_loop().run_in_executor(
            None,
            generate_ai_response,
            profile,
            message,
            interface,
            session_id,
        )
        
        return response or ""
    
    def _build_synthesis_prompt(
        self,
        previous_text: str,
        tool_name: str,
        tool_result: dict[str, Any],
    ) -> str:
        """Build a prompt for synthesis after tool execution."""
        status = "succeeded" if tool_result.get("ok") else "failed"
        markdown = tool_result.get("markdown", tool_result.get("error", "No result"))
        
        return f"""The previous command `/{tool_name}` {status}.

Tool output:
{markdown}

{previous_text}

Now provide a natural response to the user based on this tool result."""


# Singleton
_orchestrator: AgenticOrchestrator | None = None


def get_agentic_orchestrator() -> AgenticOrchestrator:
    """Get or create the singleton agentic orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgenticOrchestrator()
    return _orchestrator


async def run_agentic_loop(
    user_message: str,
    session_id: int,
    interface: str = "terminal",
) -> TurnResult:
    """Convenience function to run the agentic loop."""
    orchestrator = get_agentic_orchestrator()
    return await orchestrator.run(user_message, session_id, interface)


async def stream_agentic_loop(
    user_message: str,
    session_id: int,
    interface: str = "web",
    base64_images: list[str] | None = None,
) -> AsyncIterator[str]:
    """Stream agentic loop with structured SSE events.
    
    Yields SSE-formatted strings:
      event: thought
      data: {"content": "..."}
      
      event: command
      data: {"tool": "zo_search", "args": {...}}
      
      event: tool_result
      data: {"ok": true, "output": "..."}
      
      event: text
      data: {"chunk": "..."}
      
      event: done
      data: {"iterations": 3, "elapsed": 12.5}
    """
    orchestrator = get_agentic_orchestrator()
    
    async for event in orchestrator.run_streaming(user_message, session_id, interface, base64_images):
        yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"