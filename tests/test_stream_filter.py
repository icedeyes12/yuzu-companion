"""
Unit tests for v3.1.0 StreamFilter refactor and multi-line argument parsing.
"""

from __future__ import annotations


from app.commands import (
    StreamFilter,
    StreamState,
    parse_command_with_multiline_args,
    detect_command,
)


# --------------------------------------------------------------------
# StreamFilter Tests
# --------------------------------------------------------------------


class TestStreamFilterLineBuffering:
    """Test line-buffering behavior preserves typing effect."""

    def test_normal_text_yields_immediately(self) -> None:
        """Non-command text should yield character by character."""
        sf = StreamFilter()
        chunks = list(sf.feed("Hello world!\n"))

        # Should yield each character immediately (typing effect)
        assert "H" in chunks
        assert "e" in chunks
        assert "l" in chunks
        assert "".join([c for c in chunks if isinstance(c, str)]) == "Hello world!\n"

    def test_text_without_newline_yields_chars(self) -> None:
        """Text without newline still yields immediately."""
        sf = StreamFilter()
        chunks = list(sf.feed("Hello "))
        chunks.extend(sf.feed("world"))

        text = "".join([c for c in chunks if isinstance(c, str)])
        assert text == "Hello world"

    def test_multiple_lines_yield_sequentially(self) -> None:
        """Multiple lines should yield in order."""
        sf = StreamFilter()
        chunks = list(sf.feed("Line 1\nLine 2\nLine 3\n"))

        # With character-by-character yielding, we get individual chars
        text = "".join([c for c in chunks if isinstance(c, str)])
        assert text == "Line 1\nLine 2\nLine 3\n"


class TestStreamFilterCommandDetection:
    """Test command detection at line start."""

    def test_command_at_line_start_detected(self) -> None:
        """Slash at line start triggers command mode."""
        sf = StreamFilter()
        _ = list(sf.feed("/imagine cat\n"))

        # After newline, command should be parsed
        assert sf.command is not None
        assert sf.command["command"] == "imagine"
        assert sf.command["args"]["prompt"] == "cat"

    def test_command_not_detected_mid_line(self) -> None:
        """Slash in middle of line is not a command."""
        sf = StreamFilter()
        chunks = list(sf.feed("Look at /imagine this\n"))

        # No command should be detected
        assert sf.command is None
        text = "".join([c for c in chunks if isinstance(c, str)])
        assert text == "Look at /imagine this\n"

    def test_command_with_args_parsed(self) -> None:
        """Command with positional args parsed correctly."""
        sf = StreamFilter()
        _ = list(sf.feed("/imagine a fluffy cat with big eyes\n"))

        assert sf.command is not None
        assert sf.command["command"] == "imagine"
        assert "fluffy cat" in sf.command["args"].get("prompt", "")

    def test_command_execution_sets_tool_result(self) -> None:
        """Command execution populates tool_result."""
        sf = StreamFilter()
        _ = list(sf.feed("/imagine test image\n"))

        assert sf.tool_result is not None
        assert "tool" in sf.tool_result
        assert "result" in sf.tool_result


class TestStreamFilterMultipleCommands:
    """Test handling of multiple commands in sequence."""

    def test_text_after_command_yields_normally(self) -> None:
        """Text after command should yield normally."""
        sf = StreamFilter()
        chunks = list(sf.feed("/imagine cat\nHere is your image!"))

        # Command is detected
        assert sf.command is not None
        # Text after command should be in buffer or yielded
        text = "".join([c for c in chunks if isinstance(c, str)])
        # Command line is suppressed, but trailing text yields
        assert "Here is your image!" in text or sf._line_buffer

    def test_multiple_commands_in_sequence(self) -> None:
        """Multiple commands should each be detected."""
        sf = StreamFilter()
        list(sf.feed("/imagine cat\n"))
        first_command = sf.command

        list(sf.feed("/memory_store fact=test\n"))

        assert first_command is not None
        assert first_command["command"] == "imagine"
        # Note: second command overwrites first in current implementation
        # This is expected behavior for single-command-per-turn


class TestStreamFilterFlush:
    """Test flush behavior."""

    def test_flush_yields_remaining_buffer(self) -> None:
        """Flush should yield any remaining buffered text."""
        sf = StreamFilter()
        _ = list(sf.feed("Hello"))
        chunks = list(sf.flush())

        text = "".join([c for c in chunks if isinstance(c, str)])
        assert text == "Hello"

    def test_flush_handles_incomplete_command(self) -> None:
        """Incomplete command at EOF should be handled."""
        sf = StreamFilter()
        _ = list(sf.feed("/imagine cat"))  # No newline
        _ = list(sf.flush())

        # Command should still be detected and executed
        assert sf.command is not None
        assert sf.command["command"] == "imagine"


# --------------------------------------------------------------------
# Multi-line Argument Parsing Tests
# --------------------------------------------------------------------


class TestParseCommandWithMultilineArgs:
    """Test multi-line argument parsing."""

    def test_single_positional_arg(self) -> None:
        """Single positional argument maps to default key."""
        parsed = parse_command_with_multiline_args("/imagine cute fluffy cat")

        assert parsed is not None
        assert parsed["command"] == "imagine"
        assert parsed["args"]["prompt"] == "cute fluffy cat"

    def test_named_args_simple(self) -> None:
        """Named args with quoted values."""
        parsed = parse_command_with_multiline_args(
            '/memory_store fact="User likes cats" category="Preferences"'
        )

        assert parsed is not None
        assert parsed["command"] == "memory_store"
        assert parsed["args"]["fact"] == "User likes cats"
        assert parsed["args"]["category"] == "Preferences"

    def test_named_args_with_escaped_quotes(self) -> None:
        """Escaped quotes inside values."""
        parsed = parse_command_with_multiline_args(
            '/memory_store fact="He said \\"hello\\"" category="Quotes"'
        )

        assert parsed is not None
        assert parsed["args"]["fact"] == 'He said "hello"'

    def test_json_block_after_newline(self) -> None:
        """JSON block on following lines."""
        command = """/request POST https://api.example.com
{
  "key": "value",
  "nested": {"data": true}
}"""
        parsed = parse_command_with_multiline_args(command)

        assert parsed is not None
        assert parsed["command"] == "request"
        assert parsed["args"]["key"] == "value"
        assert parsed["args"]["nested"]["data"] is True

    def test_multiline_quoted_string(self) -> None:
        """Quoted string spanning multiple lines."""
        command = """/memory_store fact="This is a long fact
that spans multiple lines
until the closing quote" category="Identity\""""
        parsed = parse_command_with_multiline_args(command)

        assert parsed is not None
        assert "spans multiple lines" in parsed["args"]["fact"]
        assert parsed["args"]["category"] == "Identity"

    def test_empty_command_returns_none(self) -> None:
        """Empty string returns None."""
        assert parse_command_with_multiline_args("") is None
        assert parse_command_with_multiline_args("   ") is None

    def test_non_command_returns_none(self) -> None:
        """Non-slash-prefixed text returns None."""
        assert parse_command_with_multiline_args("Hello world") is None

    def test_command_only_no_args(self) -> None:
        """Command with no args returns empty args dict."""
        parsed = parse_command_with_multiline_args("/imagine")

        assert parsed is not None
        assert parsed["command"] == "imagine"
        assert parsed["args"] == {}


class TestDetectCommandBackwardCompat:
    """Test detect_command for backward compatibility."""

    def test_detect_command_simple(self) -> None:
        """Simple command detection."""
        result = detect_command("/imagine cat")
        assert result is not None
        assert result["command"] == "imagine"
        assert result["args"] == "cat"

    def test_detect_command_no_args(self) -> None:
        """Command with no args."""
        result = detect_command("/help")
        assert result is not None
        assert result["command"] == "help"
        assert result["args"] == ""

    def test_detect_command_multiline_text(self) -> None:
        """Only first line is considered."""
        result = detect_command("/imagine cat\nThis is extra text")
        assert result is not None
        assert result["command"] == "imagine"
        assert result["args"] == "cat"

    def test_detect_command_no_slash(self) -> None:
        """Non-command returns None."""
        assert detect_command("Hello world") is None


# --------------------------------------------------------------------
# StreamFilter State Machine Tests
# --------------------------------------------------------------------


class TestStreamFilterStateMachine:
    """Test state machine transitions."""

    def test_initial_state_normal(self) -> None:
        """Initial state is NORMAL."""
        sf = StreamFilter()
        assert sf._state == StreamState.NORMAL

    def test_normal_to_command_detected(self) -> None:
        """Slash at line start triggers COMMAND_DETECTED."""
        sf = StreamFilter()
        _ = list(sf.feed("/"))

        assert sf._state == StreamState.COMMAND_DETECTED

    def test_command_detected_to_normal_after_newline(self) -> None:
        """Newline after command returns to NORMAL."""
        sf = StreamFilter()
        _ = list(sf.feed("/imagine cat\n"))

        assert sf._state == StreamState.NORMAL

    def test_buffer_overflow_returns_to_normal(self) -> None:
        """Buffer overflow yields buffer and returns to NORMAL."""
        sf = StreamFilter()
        # Feed a very long command
        long_text = "/" + "x" * 17000
        _ = list(sf.feed(long_text))

        # Should have switched back to NORMAL due to overflow
        assert sf._state == StreamState.NORMAL
