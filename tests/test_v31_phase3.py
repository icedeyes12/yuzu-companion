"""
Unit tests for v3.1.0 Phase 3: StreamFilter XML Parsing & Placeholder Emission.

Tests for:
- StreamState enum
- _parse_tools_block() XML parsing
- StreamFilter <tools> detection
- Placeholder event emission
- Legacy /command backward compatibility
"""

from __future__ import annotations

import pytest

from app.commands import (
    StreamFilter,
    StreamState,
    _parse_tools_block,
)


class TestStreamState:
    """Tests for StreamState enum."""

    def test_stream_state_values(self) -> None:
        """StreamState has expected states."""
        assert hasattr(StreamState, "NORMAL")
        assert hasattr(StreamState, "TOOLS_DETECTED")
        assert hasattr(StreamState, "TOOLS_COMPLETE")

    def test_stream_state_auto_values(self) -> None:
        """StreamState auto-values are unique."""
        states = [StreamState.NORMAL, StreamState.TOOLS_DETECTED, StreamState.TOOLS_COMPLETE]
        values = [s.value for s in states]
        assert len(set(values)) == 3


class TestParseToolsBlock:
    """Tests for _parse_tools_block() XML parser."""

    def test_parse_simple_tools_block(self) -> None:
        """Parse basic <tools> block."""
        xml = "<tools><name>memory_search</name></tools>"
        result = _parse_tools_block(xml)
        assert result is not None
        assert result["name"] == "memory_search"
        assert result["args"] == {}

    def test_parse_tools_block_with_args(self) -> None:
        """Parse <tools> block with args."""
        xml = "<tools><name>memory_search</name><args><query>cats</query></args></tools>"
        result = _parse_tools_block(xml)
        assert result is not None
        assert result["name"] == "memory_search"
        assert result["args"] == {"query": "cats"}

    def test_parse_tools_block_with_multiple_args(self) -> None:
        """Parse <tools> block with multiple args."""
        xml = "<tools><name>memory_store</name><args><fact>test fact</fact><category>test</category></args></tools>"
        result = _parse_tools_block(xml)
        assert result is not None
        assert result["name"] == "memory_store"
        assert result["args"] == {"fact": "test fact", "category": "test"}

    def test_parse_tools_block_with_whitespace(self) -> None:
        """Parse <tools> block with whitespace."""
        xml = """
        <tools>
            <name>memory_search</name>
            <args>
                <query>cats</query>
            </args>
        </tools>
        """
        result = _parse_tools_block(xml)
        assert result is not None
        assert result["name"] == "memory_search"
        assert result["args"] == {"query": "cats"}

    def test_parse_invalid_tools_block(self) -> None:
        """Invalid XML returns None."""
        xml = "<tools><name>test</name>"  # Missing </tools>
        result = _parse_tools_block(xml)
        assert result is None

    def test_parse_missing_name(self) -> None:
        """Missing name returns None."""
        xml = "<tools></tools>"
        result = _parse_tools_block(xml)
        assert result is None


class TestStreamFilterNormal:
    """Tests for StreamFilter normal text processing."""

    def test_normal_text_yields_immediately(self) -> None:
        """Normal text yields during feed and flush."""
        sf = StreamFilter()
        outputs = list(sf.feed("Hello world"))
        # First part yielded during feed, rest during flush
        feed_text = "".join([o for o in outputs if isinstance(o, str)])
        flush_outputs = list(sf.flush())
        flush_text = "".join([o for o in flush_outputs if isinstance(o, str)])
        # Combined should equal original
        assert (feed_text + flush_text) == "Hello world"

    def test_multiple_chunks_yield_sequentially(self) -> None:
        """Multiple chunks yield sequentially."""
        sf = StreamFilter()
        all_outputs: list[str] = []
        for chunk in ["Hello ", "world", "!"]:
            for output in sf.feed(chunk):
                if isinstance(output, str):
                    all_outputs.append(output)
        for output in sf.flush():
            if isinstance(output, str):
                all_outputs.append(output)
        assert "".join(all_outputs) == "Hello world!"

    def test_no_tools_block_yields_all(self) -> None:
        """Text without <tools> yields completely."""
        sf = StreamFilter()
        text = "This is a normal response without tools."
        outputs: list[str] = []
        for chunk in [text[i : i + 5] for i in range(0, len(text), 5)]:
            for output in sf.feed(chunk):
                if isinstance(output, str):
                    outputs.append(output)
        for output in sf.flush():
            if isinstance(output, str):
                outputs.append(output)
        assert "".join(outputs) == text

    def test_flush_yields_remaining_buffer(self) -> None:
        """Flush yields remaining buffer."""
        sf = StreamFilter()
        list(sf.feed("Hello"))
        outputs = list(sf.flush())
        # Should yield remaining text
        text = "".join([o for o in outputs if isinstance(o, str)])
        assert text == "Hello"


class TestStreamFilterToolsDetection:
    """Tests for StreamFilter <tools> block detection."""

    def test_tools_block_detected(self) -> None:
        """StreamFilter detects <tools> block."""
        sf = StreamFilter()
        xml = "Baik, saya akan mencari.\n<tools><name>memory_search</name></tools>"
        outputs: list[str | dict] = []
        for chunk in [xml[i : i + 5] for i in range(0, len(xml), 5)]:
            for output in sf.feed(chunk):
                outputs.append(output)
        
        # Should have text before tools and placeholder event
        assert any(isinstance(o, dict) and o.get("type") == "tool_executing" for o in outputs)
        assert sf.tool_call is not None
        assert sf.tool_call["name"] == "memory_search"

    def test_tools_block_emits_placeholder(self) -> None:
        """Placeholder event is emitted when <tools> detected."""
        sf = StreamFilter()
        xml = "<tools><name>memory_search</name></tools>"
        outputs = list(sf.feed(xml))
        
        placeholder = next((o for o in outputs if isinstance(o, dict)), None)
        assert placeholder is not None
        assert placeholder["type"] == "tool_executing"
        assert placeholder["name"] == "memory_search"

    def test_text_before_tools_yields(self) -> None:
        """Text before <tools> is yielded."""
        sf = StreamFilter()
        xml = "Narrative text.\n<tools><name>test</name></tools>"
        outputs: list[str | dict] = []
        for chunk in [xml[i : i + 5] for i in range(0, len(xml), 5)]:
            for output in sf.feed(chunk):
                outputs.append(output)
        
        text_outputs = [o for o in outputs if isinstance(o, str)]
        combined = "".join(text_outputs)
        assert "Narrative" in combined

    def test_text_after_tools_yields(self) -> None:
        """Text after </tools> is yielded."""
        sf = StreamFilter()
        xml = "<tools><name>test</name></tools>After text."
        outputs: list[str | dict] = []
        for chunk in [xml[i : i + 5] for i in range(0, len(xml), 5)]:
            for output in sf.feed(chunk):
                outputs.append(output)
        
        text_outputs = [o for o in outputs if isinstance(o, str)]
        combined = "".join(text_outputs)
        assert "After text." in combined

    def test_tools_block_with_args_parsed(self) -> None:
        """Args are parsed from <tools> block."""
        sf = StreamFilter()
        xml = "<tools><name>memory_search</name><args><query>cats</query></args></tools>"
        list(sf.feed(xml))
        
        assert sf.tool_call is not None
        assert sf.tool_call["name"] == "memory_search"
        assert sf.tool_call["args"] == {"query": "cats"}

    def test_incomplete_tools_block_flush(self) -> None:
        """Incomplete <tools> block in flush is yielded as text."""
        sf = StreamFilter()
        incomplete = "<tools><name>test"
        list(sf.feed(incomplete))
        
        outputs = list(sf.flush())
        # Should yield the incomplete block as text
        text_outputs = [o for o in outputs if isinstance(o, str)]
        assert any("<tools>" in t for t in text_outputs)

    def test_no_placeholder_after_tools_complete(self) -> None:
        """No placeholder after tools block complete."""
        sf = StreamFilter()
        xml = "<tools><name>test</name></tools>more text"
        list(sf.feed(xml))
        
        # Add more text after tools complete
        outputs = list(sf.feed(" even more"))
        # Should only yield text, no placeholder
        assert all(isinstance(o, str) for o in outputs)


class TestStreamFilterLegacyCommand:
    """Tests for legacy /command backward compatibility."""

    def test_legacy_command_detected(self) -> None:
        """Legacy /command is detected."""
        sf = StreamFilter()
        text = "/imagine cute cat\n"
        outputs = list(sf.feed(text))
        
        # Command detection happens in flush
        for output in sf.flush():
            outputs.append(output)
        
        assert sf.command is not None
        assert sf.command["command"] == "imagine"
        assert sf.command["args"] == "cute cat"
        # Command text should not be yielded
        text_outputs = [o for o in outputs if isinstance(o, str)]
        assert "".join(text_outputs) == ""

    def test_legacy_command_not_in_text(self) -> None:
        """Legacy /command not at start is ignored."""
        sf = StreamFilter()
        text = "Some text\n/imagine cat\n"
        list(sf.feed(text))
        
        # command should be None since /imagine is not at start
        assert sf.command is None

    def test_legacy_command_with_tools_preferred(self) -> None:
        """<tools> block takes precedence over legacy /command."""
        sf = StreamFilter()
        xml = "Text.\n<tools><name>memory_search</name><args><query>test</query></args></tools>"
        list(sf.feed(xml))
        
        # tool_call should be set from <tools>
        assert sf.tool_call is not None
        assert sf.tool_call["name"] == "memory_search"


class TestStreamFilterEdgeCases:
    """Tests for edge cases."""

    def test_empty_chunk(self) -> None:
        """Empty chunk is handled."""
        sf = StreamFilter()
        outputs = list(sf.feed(""))
        assert outputs == []

    def test_multiple_tools_blocks(self) -> None:
        """Multiple <tools> blocks - only first is captured."""
        sf = StreamFilter()
        xml = "<tools><name>first</name></tools><tools><name>second</name></tools>"
        list(sf.feed(xml))
        
        # Should capture first tool
        assert sf.tool_call is not None
        assert sf.tool_call["name"] == "first"

    def test_tools_block_in_chunks(self) -> None:
        """<tools> block arriving in multiple chunks."""
        sf = StreamFilter()
        chunks = ["<tool", "s><nam", "e>test", "</name>", "</too", "ls>"]
        outputs: list[str | dict] = []
        for chunk in chunks:
            for output in sf.feed(chunk):
                outputs.append(output)
        
        # Should detect tools block
        assert sf.tool_call is not None or any("<tools>" in str(o) for o in outputs)

    def test_full_text_preserved(self) -> None:
        """full_text preserves all input."""
        sf = StreamFilter()
        text = "Hello <tools><name>test</name></tools> world"
        list(sf.feed(text))
        
        assert sf.full_text == text


# ---------------------------------------
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
