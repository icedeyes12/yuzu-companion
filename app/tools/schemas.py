from __future__ import annotations
# FILE: app/tools/schemas.py
# DESCRIPTION: Standard tool definition schema for function calling.
# All tools MUST expose a TOOL_DEFINITION and implement execute(arguments, session_id=None).


from dataclasses import dataclass, field
from html import escape as html_escape
from typing import Any


@dataclass
class ToolParam:
    """A single parameter for a tool's execute() function."""
    name: str
    description: str
    type: str = "string"  # string | number | boolean | object | array
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


@dataclass
class ToolDefinition:
    """Complete definition of a callable tool.

    This object is the single source of truth for:
    - The LLM's tools[] array (serialized to function-calling schema)
    - Dispatcher routing (tool_name → module)
    - Role categorization for DB storage
    - Terminal/non-terminal classification for second LLM pass
    """
    name: str  # unique, matches module name, e.g. "image_generate"
    description: str  # human-readable; LLM uses this to decide when to call
    role: str  # DB storage role, e.g. "image_tools", "request_tools"
    parameters: list[ToolParam] = field(default_factory=list)
    is_terminal: bool = False  # if True, skip second LLM pass on success

    # Internal fields (not serialized to LLM schema)
    needs_session: bool = False  # if True, dispatcher injects session_id from context

    def to_llm_schema(self) -> dict:
        """Serialize to OpenAI function-calling schema format."""
        properties = {}
        required = []

        for p in self.parameters:
            prop = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            if not p.required and p.default is not None:
                prop["default"] = p.default
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


# --------------------------------------------------------------------
# Tool result standard
# --------------------------------------------------------------------
# Every tool's execute() MUST return this shape:
#
#   {"ok": True,  "data": {...}, "markdown": "<details>...</details>"}
#   {"ok": False, "error": "...", "markdown": "<details>...</details>"}
#
# markdown is the rendered output stored in DB and shown in UI.
# --------------------------------------------------------------------



def build_tool_contract(
    tool_def: ToolDefinition,
    full_command: str,
    output_lines: list[str],
    partner_name: str = "Yuzu",
) -> str:
    """Build the unified markdown contract for tool output.

    Returns a ``<details>`` block — the ONLY format stored in DB
    and rendered by the frontend.
    """
    quoted = []
    raw = []
    for line in output_lines:
        if line.startswith("<img ") or line.startswith("<video "):
            raw.append(line)
        else:
            quoted.append(f"> {line}")
    formatted_output = "\n".join(quoted) + ("\n\n" + "\n".join(raw) if raw else "")

    return (
        f"<details>\n"
        f"<summary>🔧 {tool_def.role}</summary>\n"
        f"\n"
        f"```bash\n"
        f"{partner_name}$ {full_command}\n"
        f"```\n"
        f"\n"
        f"{formatted_output}\n"
        f"\n"
        f"</details>"
    )


def ok_result(
    data: dict,
    tool_def: ToolDefinition,
    full_command: str,
    partner_name: str = "Yuzu",
) -> dict:
    """Construct a successful tool result."""
    return {
        "ok": True,
        "data": data,
        "markdown": build_tool_contract(tool_def, full_command, _flatten_lines(data), partner_name),
    }


def error_result(
    message: str,
    tool_def: ToolDefinition,
    full_command: str,
    partner_name: str = "Yuzu",
) -> dict:
    """Construct an error tool result."""
    return {
        "ok": False,
        "error": message,
        "markdown": build_tool_contract(tool_def, full_command, [f"Error: {message}"], partner_name),
    }


def _flatten_lines(data: dict) -> list[str]:
    """Flatten a result dict into displayable lines."""
    lines = []
    for key, value in data.items():
        if isinstance(value, str) and value.startswith("<"):
            lines.append(value)
        else:
            lines.append(f"{key}: {value}")
    return lines


# --------------------------------------------------------------------
# v3.1.0 XML Format Functions
# --------------------------------------------------------------------
# Tools return XML format for LLM synthesis, markdown for UI display.
# --------------------------------------------------------------------


def sanitize_xml_value(value: str) -> str:
    """Sanitize string for safe XML element content.
    
    - XML-escapes: < > & " '
    - Removes control chars (except 0x09, 0x0A, 0x0D)
    - Removes NULL bytes
    
    Args:
        value: Raw string input
        
    Returns:
        XML-safe string
    """
    if not isinstance(value, str):
        value = str(value)
    
    # Remove NULL bytes first
    value = value.replace("\x00", "")
    
    # Remove control characters (keep tab, newline, carriage return)
    cleaned = []
    for ch in value:
        code = ord(ch)
        if code < 0x20 and code not in (0x09, 0x0A, 0x0D):
            continue  # Skip control chars
        cleaned.append(ch)
    value = "".join(cleaned)
    
    # XML escape
    return html_escape(value, quote=True)


def format_tool_result_xml(
    tool_name: str,
    status: str,
    data: dict | None = None,
    error: str | None = None,
    summary: str | None = None,
) -> str:
    """Format tool result as XML for LLM synthesis pass.
    
    Output format:
    ```xml
    <tool_result>
      <name>tool_name</name>
      <status>ok|error</status>
      <data>
        <key>value</key>
        ...
      </data>
      <summary>Human-readable summary</summary>
    </tool_result>
    ```
    
    Args:
        tool_name: Tool identifier (e.g., "memory_search")
        status: "ok" or "error"
        data: Result data dict (for ok status)
        error: Error message (for error status)
        summary: Optional human-readable summary
        
    Returns:
        XML string
    """
    lines = ["<tool_result>"]
    lines.append(f"  <name>{sanitize_xml_value(tool_name)}</name>")
    lines.append(f"  <status>{sanitize_xml_value(status)}</status>")
    
    if status == "ok" and data:
        lines.append("  <data>")
        for key, value in data.items():
            if isinstance(value, str):
                lines.append(f"    <{key}>{sanitize_xml_value(value)}</{key}>")
            elif isinstance(value, dict):
                lines.append(f"    <{key}>")
                for k, v in value.items():
                    lines.append(f"      <{k}>{sanitize_xml_value(str(v))}</{k}>")
                lines.append(f"    </{key}>")
            elif isinstance(value, list):
                lines.append(f"    <{key}>")
                for item in value[:20]:  # Limit list items
                    lines.append(f"      <item>{sanitize_xml_value(str(item))}</item>")
                if len(value) > 20:
                    lines.append(f"      <!-- {len(value) - 20} more items -->")
                lines.append(f"    </{key}>")
            else:
                lines.append(f"    <{key}>{sanitize_xml_value(str(value))}</{key}>")
        lines.append("  </data>")
    
    if status == "error" and error:
        lines.append(f"  <error>{sanitize_xml_value(error)}</error>")
    
    if summary:
        lines.append(f"  <summary>{sanitize_xml_value(summary)}</summary>")
    
    lines.append("</tool_result>")
    return "\n".join(lines)


def dual_format_result(
    tool_def: ToolDefinition,
    full_command: str,
    data: dict,
    error: str | None = None,
    partner_name: str = "Yuzu",
    summary: str | None = None,
) -> dict:
    """Return dual-format tool result: XML + markdown.
    
    v3.1.0: Returns both formats for backward compatibility.
    
    Args:
        tool_def: Tool definition
        full_command: Full command string
        data: Result data
        error: Optional error message
        partner_name: Partner name for display
        summary: Optional summary for XML
        
    Returns:
        {
            "ok": bool,
            "data": dict,
            "error": str | None,
            "markdown": str,  # For UI
            "xml": str,       # For LLM synthesis
        }
    """
    is_ok = error is None
    
    # Markdown for UI (backward compat)
    if is_ok:
        markdown = build_tool_contract(tool_def, full_command, _flatten_lines(data), partner_name)
    else:
        markdown = build_tool_contract(tool_def, full_command, [f"Error: {error}"], partner_name)
    
    # XML for LLM
    xml = format_tool_result_xml(
        tool_name=tool_def.name,
        status="ok" if is_ok else "error",
        data=data if is_ok else None,
        error=error if not is_ok else None,
        summary=summary,
    )
    
    result = {
        "ok": is_ok,
        "data": data,
        "markdown": markdown,
        "xml": xml,
    }
    
    if error:
        result["error"] = error
    
    return result