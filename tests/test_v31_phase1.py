"""
Unit tests for v3.1.0 Phase 1: Infrastructure - XML Format & Storage

Tests:
- sanitize_xml_value()
- format_tool_result_xml()
- dual_format_result()
- tool_role_for() with use_universal
- TOOL_ROLE_UNIVERSAL constant
"""

from __future__ import annotations

import pytest

from app.tools.schemas import (
    sanitize_xml_value,
    format_tool_result_xml,
    dual_format_result,
    ToolDefinition,
    ToolParam,
)
from app.database.db_queries import (
    TOOL_ROLE_UNIVERSAL,
    tool_role_for,
)


# --------------------------------------------------------------------
# Test sanitize_xml_value()
# --------------------------------------------------------------------

class TestSanitizeXmlValue:
    """Tests for XML sanitization."""
    
    def test_escapes_special_chars(self) -> None:
        """Should escape < > & " ' """
        result = sanitize_xml_value('a & b < c > d "e" \'f\'')
        assert "&amp;" in result
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&quot;" in result
        assert "&#x27;" in result
    
    def test_removes_null_bytes(self) -> None:
        """Should remove NULL bytes."""
        result = sanitize_xml_value("hello\x00world")
        assert "\x00" not in result
        assert result == "helloworld"
    
    def test_removes_control_chars(self) -> None:
        """Should remove control characters except tab, newline, CR."""
        result = sanitize_xml_value("hello\x01\x02\x03world")
        assert result == "helloworld"
    
    def test_preserves_newline_tab_cr(self) -> None:
        """Should preserve newline, tab, and carriage return."""
        result = sanitize_xml_value("line1\nline2\ttab\r\n")
        assert "\n" in result
        assert "\t" in result
        assert "\r" in result
    
    def test_non_string_converts_to_string(self) -> None:
        """Should convert non-string input to string."""
        assert sanitize_xml_value(123) == "123"
        assert sanitize_xml_value(True) == "True"
        assert sanitize_xml_value(None) == "None"


# --------------------------------------------------------------------
# Test format_tool_result_xml()
# --------------------------------------------------------------------

class TestFormatToolResultXml:
    """Tests for XML result formatting."""
    
    def test_ok_result_basic(self) -> None:
        """Should format successful result."""
        xml = format_tool_result_xml(
            tool_name="memory_search",
            status="ok",
            data={"count": 5, "results": ["mem1", "mem2"]},
            summary="Found 5 memories",
        )
        
        assert "<tool_result>" in xml
        assert "<name>memory_search</name>" in xml
        assert "<status>ok</status>" in xml
        assert "<data>" in xml
        assert "<count>5</count>" in xml
        assert "<summary>Found 5 memories</summary>" in xml
        assert "</tool_result>" in xml
    
    def test_error_result(self) -> None:
        """Should format error result."""
        xml = format_tool_result_xml(
            tool_name="image_generate",
            status="error",
            error="API key not configured",
        )
        
        assert "<status>error</status>" in xml
        assert "<error>API key not configured</error>" in xml
        assert "<data>" not in xml
    
    def test_escapes_data_values(self) -> None:
        """Should escape special chars in data values."""
        xml = format_tool_result_xml(
            tool_name="test",
            status="ok",
            data={"query": "cats & dogs <test>"},
        )
        
        assert "&amp;" in xml
        assert "&lt;" in xml
        assert "&gt;" in xml
    
    def test_limits_list_items(self) -> None:
        """Should limit list items to 20."""
        items = [f"item{i}" for i in range(50)]
        xml = format_tool_result_xml(
            tool_name="test",
            status="ok",
            data={"items": items},
        )
        
        assert "<item>item0</item>" in xml
        assert "<item>item19</item>" in xml
        assert "30 more items" in xml
    
    def test_nested_dict(self) -> None:
        """Should handle nested dict values."""
        xml = format_tool_result_xml(
            tool_name="test",
            status="ok",
            data={"meta": {"key": "value", "num": 123}},
        )
        
        assert "<meta>" in xml
        assert "<key>value</key>" in xml
        assert "<num>123</num>" in xml


# --------------------------------------------------------------------
# Test dual_format_result()
# --------------------------------------------------------------------

class TestDualFormatResult:
    """Tests for dual-format result (XML + markdown)."""
    
    @pytest.fixture
    def tool_def(self) -> ToolDefinition:
        """Create a test tool definition."""
        return ToolDefinition(
            name="memory_search",
            description="Search memories",
            role="memory_tools",
            parameters=[
                ToolParam(name="query", description="Search query"),
            ],
        )
    
    def test_returns_both_formats(self, tool_def: ToolDefinition) -> None:
        """Should return both markdown and XML formats."""
        result = dual_format_result(
            tool_def=tool_def,
            full_command="/memory_search cats",
            data={"count": 3},
        )
        
        assert "markdown" in result
        assert "xml" in result
        assert result["ok"] is True
        assert "<tool_result>" in result["xml"]
        assert "<details>" in result["markdown"]
    
    def test_error_result_dual(self, tool_def: ToolDefinition) -> None:
        """Should format error in both formats."""
        result = dual_format_result(
            tool_def=tool_def,
            full_command="/memory_search",
            data={},
            error="Query required",
        )
        
        assert result["ok"] is False
        assert result["error"] == "Query required"
        assert "<status>error</status>" in result["xml"]


# --------------------------------------------------------------------
# Test tool_role_for()
# --------------------------------------------------------------------

class TestToolRoleFor:
    """Tests for tool role lookup."""
    
    def test_known_tool_old_behavior(self) -> None:
        """Should return specific role for known tool."""
        assert tool_role_for("image_generate") == "image_tools"
        assert tool_role_for("imagine") == "image_tools"
        assert tool_role_for("request") == "request_tools"
    
    def test_unknown_tool_old_behavior(self) -> None:
        """Should return {name}_tools for unknown tool."""
        assert tool_role_for("unknown_tool") == "unknown_tool_tools"
    
    def test_universal_role_flag(self) -> None:
        """Should return 'tools' when use_universal=True."""
        assert tool_role_for("image_generate", use_universal=True) == "tools"
        assert tool_role_for("unknown_tool", use_universal=True) == "tools"
    
    def test_universal_constant_exists(self) -> None:
        """TOOL_ROLE_UNIVERSAL should be 'tools'."""
        assert TOOL_ROLE_UNIVERSAL == "tools"


# --------------------------------------------------------------------
# Run tests
# --------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
