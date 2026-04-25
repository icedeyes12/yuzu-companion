# FILE: tests/test_agents_phase1.py
# DESCRIPTION: Verify Phase 1+2 agentic components work correctly

import pytest

from app.agents import (
    parse_thought,
    extract_thought_and_response,
    parse_command,
    parse_bracket_command,
    parse_slash_command,
    AgentConfig,
    get_agent_config,
    ToolCall,
    StreamMeta,
    create_stream_parser,
)
from app.mcp.client import MCPClient, MCPTool
from app.dispatch import HybridDispatcher, get_dispatcher


class TestThoughtParser:
    """Test <thought> block parsing."""
    
    def test_parse_simple_thought(self):
        text = """<thought>
Planning: I need to search for information
Tools: zo_search
</thought>

[COMMAND: zo_search(query="hello")]"""
        
        thought = parse_thought(text)
        assert thought is not None
        assert "Planning:" in thought.content
        assert thought.planning == "I need to search for information"
        assert "zo_search" in thought.tools_mentioned
    
    def test_parse_no_thought(self):
        text = "Just a regular response without thoughts."
        thought = parse_thought(text)
        assert thought is None
    
    def test_extract_thought_and_response(self):
        text = """<thought>
Planning: Need to search
</thought>

Here is the actual response."""
        
        thought, response = extract_thought_and_response(text)
        assert thought is not None
        assert "Planning" in thought.content
        assert "actual response" in response
    
    def test_strip_thought_blocks(self):
        from app.agents import strip_thought_blocks
        
        text = """<thought>Secret reasoning</thought>

Public response"""
        
        cleaned = strip_thought_blocks(text)
        assert "Secret reasoning" not in cleaned
        assert "Public response" in cleaned


class TestCommandParser:
    """Test [COMMAND: ...] and /command parsing."""
    
    def test_parse_bracket_command(self):
        text = '[COMMAND: imagine(prompt="a cute cat")]'
        cmd = parse_bracket_command(text)
        assert cmd is not None
        assert cmd.tool_name == "imagine"
        assert cmd.arguments == {"prompt": "a cute cat"}
    
    def test_parse_bracket_command_multiple_args(self):
        text = '[COMMAND: memory_store(fact="test", category="personal")]'
        cmd = parse_bracket_command(text)
        assert cmd is not None
        assert cmd.tool_name == "memory_store"
        assert cmd.arguments == {"fact": "test", "category": "personal"}
    
    def test_parse_bracket_command_complex(self):
        text = '''[COMMAND: zo_search(query="what is rust programming language", limit=5)]'''
        cmd = parse_bracket_command(text)
        assert cmd is not None
        assert cmd.tool_name == "zo_search"
        assert cmd.arguments.get("query") == "what is rust programming language"
        assert cmd.arguments.get("limit") == 5
    
    def test_parse_slash_command(self):
        text = "/imagine a cute cat"
        cmd = parse_slash_command(text)
        assert cmd is not None
        assert cmd.tool_name == "imagine"
        assert cmd.arguments == {"prompt": "a cute cat"}
    
    def test_parse_command_auto_detect_bracket(self):
        text = '[COMMAND: zo_search(query="test")]'
        cmd = parse_command(text)
        assert cmd is not None
        assert cmd.tool_name == "zo_search"
    
    def test_parse_command_auto_detect_slash(self):
        text = "/request GET https://example.com"
        cmd = parse_command(text)
        assert cmd is not None
        assert cmd.tool_name == "request"
    
    def test_parse_command_no_command(self):
        text = "Just a regular response"
        cmd = parse_command(text)
        assert cmd is None
    
    def test_strip_command(self):
        from app.agents import strip_command, parse_command
        
        text = """[COMMAND: imagine(prompt="cat")]

Some response text"""
        
        cmd = parse_command(text)
        cleaned = strip_command(text, cmd)
        assert "[COMMAND:" not in cleaned
        assert "Some response text" in cleaned


class TestAgentConfig:
    """Test agentic loop configuration."""
    
    def test_default_config(self):
        config = get_agent_config()
        assert config.max_iterations == 50
        assert config.total_timeout_seconds == 1800
        assert config.enable_mcp is True
    
    def test_custom_config(self):
        config = AgentConfig(
            max_iterations=10,
            total_timeout_seconds=300,
        )
        assert config.max_iterations == 10
        assert config.total_timeout_seconds == 300


class TestMCPClient:
    """Test MCP HTTP client."""
    
    def test_client_init_no_token(self):
        """Client should work gracefully without token."""
        import os
        # Save and remove token if present
        old_token = os.environ.pop("ZO_ACCESS_TOKEN", None)
        
        client = MCPClient()
        assert client.token is None or client.token == ""
        
        # Restore token
        if old_token:
            os.environ["ZO_ACCESS_TOKEN"] = old_token
    
    def test_client_init_with_token(self):
        """Client with token should be available."""
        import os
        old_token = os.environ.get("ZO_ACCESS_TOKEN")
        os.environ["ZO_ACCESS_TOKEN"] = "test_token_123"
        
        client = MCPClient()
        assert client.token == "test_token_123"
        
        # Restore
        if old_token:
            os.environ["ZO_ACCESS_TOKEN"] = old_token
        else:
            del os.environ["ZO_ACCESS_TOKEN"]
    
    def test_mcp_tool_dataclass(self):
        tool = MCPTool(
            name="zo_search",
            description="Web search",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        )
        assert tool.name == "zo_search"
        assert tool.description == "Web search"


class TestHybridDispatcher:
    """Test hybrid local/MCP dispatcher."""
    
    def test_dispatcher_initialization(self):
        """Dispatcher should initialize with local tools."""
        dispatcher = HybridDispatcher()
        # Should initialize empty, lazy-load on first use
        assert dispatcher._local_tools == {}
        assert dispatcher._mcp_tools == {}
        assert dispatcher._initialized is False
    
    def test_is_local_tool_lazy(self):
        """Should correctly identify local tools even without init."""
        dispatcher = HybridDispatcher()
        # Lazy fallback for unimplemented tools
        assert dispatcher.is_local_tool("image_generate") is True
        assert dispatcher.is_local_tool("imagine") is True  # alias
        assert dispatcher.is_local_tool("http_request") is True
        assert dispatcher.is_local_tool("request") is True  # alias
    
    def test_is_mcp_tool_without_mcp(self):
        """Should return False for MCP tools when MCP unavailable."""
        dispatcher = HybridDispatcher()
        # Without MCP initialized
        assert dispatcher.is_mcp_tool("zo_search") is False
    
    def test_execute_unknown_tool(self):
        """Should return error for unknown tools."""
        import asyncio
        
        dispatcher = HybridDispatcher()
        result = asyncio.run(dispatcher.execute("unknown_tool_xyz", {}))
        
        assert result.get("ok") is False
        assert "Unknown tool" in result.get("error", "")
    
    def test_get_all_tools_empty_before_init(self):
        """Should return empty list before initialization."""
        dispatcher = HybridDispatcher()
        tools = dispatcher.get_all_tools()
        assert tools == []  # Not initialized yet


class TestIntegration:
    """Integration tests for the full agentic stack."""
    
    def test_full_parse_and_dispatch_flow(self):
        """Test the full flow: parse thought → parse command → prepare dispatch."""
        response = """<thought>
Planning: User wants an image
Tools: imagine
</thought>

[COMMAND: imagine(prompt="a cute anime cat")]"""
        
        # Parse thought
        thought = parse_thought(response)
        assert thought is not None
        assert "imagine" in thought.tools_mentioned
        
        # Parse command
        cmd = parse_command(response)
        assert cmd is not None
        assert cmd.tool_name == "imagine"
        assert cmd.arguments.get("prompt") == "a cute anime cat"
        
        # Get dispatcher (won't actually execute, just verify structure)
        dispatcher = get_dispatcher()
        assert dispatcher.is_local_tool(cmd.tool_name)


class TestAgenticStreamParser:
    """Test buffer-based streaming parser."""
    
    def test_parser_init(self):
        """Parser should initialize cleanly."""
        parser = create_stream_parser()
        assert parser.full_text == ""
        assert parser.commands == []
        assert parser.thoughts == []
    
    def test_single_chunk_command(self):
        """Parse command in single chunk."""
        parser = create_stream_parser()
        
        chunks = list(parser.feed("[COMMAND: imagine(prompt='a cat')]"))
        assert len(chunks) == 1
        
        text, meta = chunks[0]
        assert text == ""  # Command is suppressed
        assert meta.command is not None
        assert meta.command.tool_name == "imagine"
        assert meta.command.arguments.get("prompt") == "a cat"
    
    def test_split_command_across_chunks(self):
        """Parse command split across multiple chunks."""
        parser = create_stream_parser()
        
        # Chunk 1: "[COMMAND: imag"
        chunks1 = list(parser.feed("[COMMAND: imag"))
        assert len(chunks1) == 0  # Nothing safe to emit yet
        
        # Chunk 2: "ine(prompt='a cat')] and some text"
        chunks2 = list(parser.feed("ine(prompt='a cat')] and some text"))
        
        # Should emit command + trailing text
        assert len(chunks2) == 2
        
        # First: command metadata
        text1, meta1 = chunks2[0]
        assert text1 == ""
        assert meta1.command is not None
        assert meta1.command.tool_name == "imagine"
        
        # Second: trailing text
        text2, meta2 = chunks2[1]
        assert text2 == " and some text"
    
    def test_multiple_commands_in_stream(self):
        """Parse multiple commands in sequence."""
        parser = create_stream_parser()
        
        stream = (
            "Some text\n"
            "[COMMAND: imagine(prompt='cat')]\n"
            "More text\n"
            "[COMMAND: request(url='https://example.com')]\n"
            "Final text"
        )
        
        all_chunks = []
        for chunk in stream.split("\n"):
            all_chunks.extend(parser.feed(chunk + "\n"))
        
        all_chunks.extend(parser.flush())
        
        # Should have 2 commands
        commands = [m.command for _, m in all_chunks if m.command]
        
        assert len(commands) == 2
        # Verify we got the right commands
        assert commands[0].tool_name == "imagine"
        assert commands[1].tool_name == "request"
    
    def test_thought_block_parsing(self):
        """Parse <thought> block from stream."""
        parser = create_stream_parser()
        
        # Realistic streaming: complete lines
        stream = [
            "<thought>\n",
            "Planning: Need to search\n",
            "Tools: zo_search\n",
            "</thought>\n",
            "[COMMAND: zo_search(query='rust')]",
        ]
        
        all_chunks = []
        for chunk in stream:
            all_chunks.extend(parser.feed(chunk))
        
        all_chunks.extend(parser.flush())
        
        # Should have 1 thought + 1 command
        thoughts = [m.thought for _, m in all_chunks if m.thought]
        commands = [m.command for _, m in all_chunks if m.command]
        
        assert len(thoughts) == 1
        assert len(commands) == 1
        assert thoughts[0].planning == "Need to search"
    
    def test_nested_parentheses_in_command(self):
        """Handle nested parens in command args."""
        parser = create_stream_parser()
        
        # Command with nested function call in description
        cmd = "[COMMAND: request(url='https://api.example.com/data', method='GET')]"
        
        chunks = list(parser.feed(cmd))
        chunks.extend(parser.flush())
        
        commands = [m.command for _, m in chunks if m.command]
        assert len(commands) == 1
        assert commands[0].tool_name == "request"
    
    def test_incomplete_command_at_stream_end(self):
        """Gracefully handle incomplete command at end."""
        parser = create_stream_parser()
        
        # Incomplete command (missing closing bracket)
        chunks = list(parser.feed("[COMMAND: imagine(prompt='a cat'"))
        chunks.extend(parser.flush())
        
        # Should still try to parse
        commands = [m.command for _, m in chunks if m.command]
        assert len(commands) == 1  # Gracefully parsed
        assert commands[0].tool_name == "imagine"
    
    def test_mixed_text_and_commands(self):
        """Parse mixed content correctly."""
        parser = create_stream_parser()
        
        stream = [
            "Hello! Let me generate an image.\n",
            "[COMMAND: imagine(prompt='anime cat')]\n",
            "Here's your image!\n",
        ]
        
        all_chunks = []
        for chunk in stream:
            all_chunks.extend(parser.feed(chunk))
        all_chunks.extend(parser.flush())
        
        # Verify full_text assembled correctly
        assert "Hello" in parser.full_text
        assert "Here's your image" in parser.full_text
        assert len(parser.commands) == 1


class TestStreamMeta:
    """Test StreamMeta dataclass."""
    
    def test_default_meta(self):
        """Default meta should be empty."""
        meta = StreamMeta()
        assert meta.thought is None
        assert meta.command is None
        assert meta.is_complete is False
    
    def test_meta_with_command(self):
        """Meta can hold command."""
        cmd = ToolCall(tool_name="test", arguments={}, raw_text="", format_type="bracket")
        meta = StreamMeta(command=cmd)
        assert meta.command.tool_name == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
