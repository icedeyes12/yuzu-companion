"""
Unit tests for v3.1.0 Phase 1: Infrastructure - XML Format & Storage.

Tests for:
- sanitize_xml_value()
- format_tool_result_xml()
- dual_format_result()
- TOOL_ROLE_UNIVERSAL
- tool_role_for(use_universal=True)
"""

import pytest
from app.tools.schemas import (
    sanitize_xml_value,
    format_tool_result_xml,
    dual_format_result,
    ToolDefinition,
    ok_result,
    error_result,
)
from app.database.db_queries import TOOL_ROLE_UNIVERSAL, tool_role_for


class TestXMLSanitization:
    """Tests for sanitize_xml_value()."""

    def test_escapes_xml_chars(self):
        assert sanitize_xml_value("<tag>") == "&lt;tag&gt;"
        assert sanitize_xml_value("a & b") == "a &amp; b"
        assert sanitize_xml_value('"quoted"') == "&quot;quoted&quot;"
        assert sanitize_xml_value("'single'") == "&#x27;single&#x27;"

    def test_removes_null_bytes(self):
        assert sanitize_xml_value("hello\x00world") == "helloworld"

    def test_removes_control_chars(self):
        # Keep tab, newline, CR
        assert sanitize_xml_value("a\tb\nc\rd") == "a\tb\nc\rd"
        # Remove other control chars
        assert sanitize_xml_value("a\x01b\x02c") == "abc"

    def test_non_string_input(self):
        assert sanitize_xml_value(123) == "123"
        assert sanitize_xml_value(None) == "None"


class TestFormatToolResultXML:
    """Tests for format_tool_result_xml()."""

    def test_ok_result_basic(self):
        xml = format_tool_result_xml(
            tool_name="memory_search",
            status="ok",
            data={"count": 3, "results": ["mem1", "mem2"]},
        )
        assert "<name>memory_search</name>" in xml
        assert "<status>ok</status>" in xml
        assert "<count>3</count>" in xml
        assert "<results>" in xml
        assert "<item>mem1</item>" in xml

    def test_error_result(self):
        xml = format_tool_result_xml(
            tool_name="image_generate",
            status="error",
            error="API key missing",
        )
        assert "<status>error</status>" in xml
        assert "<error>API key missing</error>" in xml

    def test_summary_included(self):
        xml = format_tool_result_xml(
            tool_name="memory_search",
            status="ok",
            data={"count": 10},
            summary="Found 10 memories",
        )
        assert "<summary>Found 10 memories</summary>" in xml

    def test_list_limited_to_20(self):
        items = [f"item{i}" for i in range(30)]
        xml = format_tool_result_xml(
            tool_name="test",
            status="ok",
            data={"items": items},
        )
        # Should have 20 items + comment about 10 more
        assert "<item>item19</item>" in xml
        assert "10 more items" in xml

    def test_nested_dict(self):
        xml = format_tool_result_xml(
            tool_name="test",
            status="ok",
            data={"nested": {"key": "value"}},
        )
        assert "<nested>" in xml
        assert "<key>value</key>" in xml


class TestDualFormatResult:
    """Tests for dual_format_result()."""

    @pytest.fixture
    def tool_def(self):
        return ToolDefinition(
            name="test_tool",
            description="Test tool",
            role="test_tools",
        )

    def test_returns_both_formats(self, tool_def):
        result = dual_format_result(
            tool_def=tool_def,
            full_command="/test_tool arg1",
            data={"result": "success"},
        )
        assert "markdown" in result
        assert "xml" in result
        assert result["ok"] is True
        assert "<details>" in result["markdown"]
        assert "<tool_result>" in result["xml"]

    def test_error_includes_both_formats(self, tool_def):
        result = dual_format_result(
            tool_def=tool_def,
            full_command="/test_tool arg1",
            data={},
            error="Something went wrong",
        )
        assert result["ok"] is False
        assert "Error:" in result["markdown"]
        assert "<status>error</status>" in result["xml"]


class TestOkErrorResultDualFormat:
    """Tests for ok_result() and error_result() dual format."""

    @pytest.fixture
    def tool_def(self):
        return ToolDefinition(
            name="test_tool",
            description="Test tool",
            role="test_tools",
        )

    def test_ok_result_has_xml(self, tool_def):
        result = ok_result(
            data={"count": 5},
            tool_def=tool_def,
            full_command="/test_tool",
        )
        assert result["ok"] is True
        assert "markdown" in result
        assert "xml" in result
        assert "<tool_result>" in result["xml"]
        assert "<status>ok</status>" in result["xml"]

    def test_error_result_has_xml(self, tool_def):
        result = error_result(
            message="Failed",
            tool_def=tool_def,
            full_command="/test_tool",
        )
        assert result["ok"] is False
        assert "xml" in result
        assert "<status>error</status>" in result["xml"]
        assert "<error>Failed</error>" in result["xml"]


class TestUniversalStorageRole:
    """Tests for TOOL_ROLE_UNIVERSAL and tool_role_for()."""

    def test_universal_role_constant(self):
        assert TOOL_ROLE_UNIVERSAL == "tools"

    def test_tool_role_for_default(self):
        # Default behavior - per-tool role
        role = tool_role_for("image_generate", use_universal=False)
        assert role == "image_tools"  # or whatever the tool defines

    def test_tool_role_for_universal(self):
        # Universal role for v3.1.0
        role = tool_role_for("image_generate", use_universal=True)
        assert role == "tools"

    def test_tool_role_for_unknown_tool(self):
        role = tool_role_for("unknown_tool_xyz", use_universal=True)
        assert role == "tools"


# --------------------------------------------------------------------
# Run tests
# --------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
