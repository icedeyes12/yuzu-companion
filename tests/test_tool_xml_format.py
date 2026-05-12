"""
Unit tests for v3.1.0 XML tool result formatting and dual-path history reader.
"""

from __future__ import annotations

import pytest

from app.tools.schemas import (
    sanitize_xml_value,
    format_tool_result_xml,
    truncate_tool_result,
    ok_result,
    error_result,
    ToolDefinition,
)
from app.database.db_queries import (
    format_ai_history_rows,
    TOOL_ROLE_UNIVERSAL,
    _parse_xml_tool_result,
)


# ---------------------------------------------------------------------------
# XML Sanitization Tests
# ---------------------------------------------------------------------------


def test_sanitize_xml_entities():
    """XML entities must be escaped."""
    assert sanitize_xml_value("a & b") == "a &amp; b"
    assert sanitize_xml_value("a < b") == "a &lt; b"
    assert sanitize_xml_value("a > b") == "a &gt; b"


def test_sanitize_xml_multiple_entities():
    """Multiple entities must all be escaped."""
    input_val = "if (a < b && c > d)"
    expected = "if (a &lt; b &amp;&amp; c &gt; d)"
    assert sanitize_xml_value(input_val) == expected


def test_sanitize_xml_control_chars():
    """Invalid control characters must be stripped."""
    # NULL byte
    assert sanitize_xml_value("hello\x00world") == "helloworld"
    # Other control chars
    assert sanitize_xml_value("hello\x01\x02world") == "helloworld"
    # Valid whitespace preserved
    assert sanitize_xml_value("hello\nworld\t") == "hello\nworld\t"


def test_sanitize_xml_non_string():
    """Non-string values are converted to string."""
    assert sanitize_xml_value(123) == "123"
    assert sanitize_xml_value(3.14) == "3.14"
    assert sanitize_xml_value(True) == "True"


# ---------------------------------------------------------------------------
# XML Tool Result Formatting Tests
# ---------------------------------------------------------------------------


def test_format_tool_result_xml_ok():
    """OK result formats as expected."""
    xml = format_tool_result_xml(
        tool_name="image_generate",
        status="ok",
        data={"path": "/images/test.png", "width": 512},
        command="/imagine a sunset",
    )
    
    assert '<tool_result name="image_generate" status="ok">' in xml
    assert "<command>/imagine a sunset</command>" in xml
    assert "<data>" in xml
    assert "<path>/images/test.png</path>" in xml
    assert "<width>512</width>" in xml
    assert "</tool_result>" in xml


def test_format_tool_result_xml_error():
    """Error result formats as expected."""
    xml = format_tool_result_xml(
        tool_name="http_request",
        status="error",
        error="Connection timeout",
        command="/request GET https://example.com",
    )
    
    assert '<tool_result name="http_request" status="error">' in xml
    assert "<error>Connection timeout</error>" in xml
    assert "<data>" not in xml


def test_format_tool_result_xml_truncation():
    """Long values are truncated."""
    long_value = "x" * 5000
    xml = format_tool_result_xml(
        tool_name="test",
        status="ok",
        data={"content": long_value},
        truncate=True,
    )
    
    assert len(xml) < 6000  # Should be truncated
    assert "[truncated]" in xml


def test_format_tool_result_xml_list():
    """List values create multiple elements."""
    xml = format_tool_result_xml(
        tool_name="memory_search",
        status="ok",
        data={"results": ["item1", "item2", "item3"]},
    )
    
    assert "<results>item1</results>" in xml
    assert "<results>item2</results>" in xml
    assert "<results>item3</results>" in xml


def test_format_tool_result_xml_nested_dict():
    """Nested dicts are flattened with dot notation."""
    xml = format_tool_result_xml(
        tool_name="test",
        status="ok",
        data={"response": {"status": 200, "body": "OK"}},
    )
    
    assert "<response.status>200</response.status>" in xml
    assert "<response.body>OK</response.body>" in xml


# ---------------------------------------------------------------------------
# Truncation Tests
# ---------------------------------------------------------------------------


def test_truncate_under_limit():
    """Under-limit content is unchanged."""
    content = "short content"
    assert truncate_tool_result(content) == content


def test_truncate_over_limit():
    """Over-limit content is truncated with marker."""
    content = "x" * 5000
    result = truncate_tool_result(content, max_chars=100)
    assert len(result) < 120
    assert result.endswith("\n... [truncated]")


# ---------------------------------------------------------------------------
# Dual-format Result Tests
# ---------------------------------------------------------------------------


def test_ok_result_dual_format():
    """ok_result returns both markdown and XML formats."""
    tool_def = ToolDefinition(
        name="test_tool",
        description="A test tool",
        role="test_tools",
    )
    
    result = ok_result(
        data={"key": "value"},
        tool_def=tool_def,
        full_command="/test arg",
        partner_name="Yuzu",
    )
    
    assert result["ok"] is True
    assert "markdown" in result
    assert "xml" in result
    assert "<details>" in result["markdown"]
    assert "<tool_result" in result["xml"]


def test_error_result_dual_format():
    """error_result returns both markdown and XML formats."""
    tool_def = ToolDefinition(
        name="test_tool",
        description="A test tool",
        role="test_tools",
    )
    
    result = error_result(
        message="Something went wrong",
        tool_def=tool_def,
        full_command="/test arg",
        partner_name="Yuzu",
    )
    
    assert result["ok"] is False
    assert "error" in result
    assert "markdown" in result
    assert "xml" in result
    assert "Error: Something went wrong" in result["markdown"]
    assert 'status="error"' in result["xml"]


# ---------------------------------------------------------------------------
# Dual-Path History Reader Tests
# ---------------------------------------------------------------------------


def test_format_ai_history_legacy_tool_role():
    """Legacy tool-role rows expand correctly."""
    rows = [
        {"role": "user", "content": "Hello", "timestamp": "2026-05-12 10:00:00"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "image_tools", "content": "<details><summary>🔧 image_tools</summary>\n```bash\nYuzu$ /imagine a sunset\n```\n\n> path: /images/sunset.png\n</details>"},
    ]
    
    formatted = format_ai_history_rows(rows)
    
    # Should expand tool role into 2 entries
    assert len(formatted) == 4  # user, assistant, assistant (/command), image_tools
    assert formatted[2]["role"] == "assistant"
    assert "/imagine" in formatted[2]["content"]
    assert formatted[3]["role"] == "image_tools"


def test_format_ai_history_new_xml_format():
    """New XML tool results expand correctly."""
    xml_result = format_tool_result_xml(
        tool_name="image_generate",
        status="ok",
        data={"path": "/images/test.png"},
        command="/imagine a sunset",
    )
    
    rows = [
        {"role": "user", "content": "Hello", "timestamp": "2026-05-12 10:00:00"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": TOOL_ROLE_UNIVERSAL, "content": xml_result},
    ]
    
    formatted = format_ai_history_rows(rows)
    
    # Should expand into assistant (/command) + tools (XML)
    assert len(formatted) == 4
    assert formatted[2]["role"] == "assistant"
    assert "/imagine" in formatted[2]["content"]
    assert formatted[3]["role"] == "tools"
    assert "<tool_result" in formatted[3]["content"]


def test_parse_xml_tool_result():
    """XML tool result parsing works."""
    xml = format_tool_result_xml(
        tool_name="http_request",
        status="ok",
        data={"status": 200, "body": "OK"},
        command="/request GET https://example.com",
    )
    
    parsed = _parse_xml_tool_result(xml)
    
    assert parsed["tool_name"] == "http_request"
    assert parsed["status"] == "ok"
    assert parsed["command"] == "/request GET https://example.com"
    assert parsed["data"] is not None


def test_parse_xml_tool_result_error():
    """XML tool error result parsing works."""
    xml = format_tool_result_xml(
        tool_name="test",
        status="error",
        error="Something went wrong",
    )
    
    parsed = _parse_xml_tool_result(xml)
    
    assert parsed["status"] == "error"
    assert parsed["error"] == "Something went wrong"


def test_format_ai_history_user_timestamp():
    """User messages get timestamp appended."""
    rows = [
        {"role": "user", "content": "Hello", "timestamp": "2026-05-12 10:00:00"},
    ]
    
    formatted = format_ai_history_rows(rows)
    
    assert len(formatted) == 1
    assert formatted[0]["role"] == "user"
    assert "Hello" in formatted[0]["content"]
    assert "[2026-05-12 10:00:00]" in formatted[0]["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
