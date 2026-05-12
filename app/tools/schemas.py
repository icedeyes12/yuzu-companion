from __future__ import annotations
# FILE: app/tools/schemas.py
# DESCRIPTION: Standard tool definition schema for function calling.
# All tools MUST expose a TOOL_DEFINITION and implement execute(arguments, session_id=None).


from dataclasses import dataclass, field
from typing import Any
import re


# --------------------------------------------------------------------
# XML Sanitization (v3.1.0 — Universal Inline Command Refactor)
# --------------------------------------------------------------------

# Invalid control chars (0x00-0x1F except 0x09, 0x0A, 0x0D)
_INVALID_XML_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_xml_value(value: str) -> str:
    """
    Sanitize a string for safe inclusion in XML element content.

    Handles:
    - XML entities: & → &amp;, < → &lt;, > → &gt;, " → &quot;, ' → &apos;
    - Invalid control characters (0x00-0x1F except 0x09, 0x0A, 0x0D): stripped
    - NULL bytes: removed

    This is NOT for attribute values — for those, wrap with double quotes.
    """
    if not isinstance(value, str):
        value = str(value)

    # Remove invalid control characters
    value = _INVALID_XML_CHARS.sub("", value)

    # Escape XML entities (order matters: & must be first)
    value = value.replace("&", "&amp;")
    value = value.replace("<", "&lt;")
    value = value.replace(">", "&gt;")

    return value


def _sanitize_xml_attribute(value: str) -> str:
    """Sanitize for XML attribute values (escapes quotes)."""
    value = sanitize_xml_value(value)
    value = value.replace('"', "&quot;")
    value = value.replace("'", "&apos;")
    return value


# --------------------------------------------------------------------
# XML Tool Result Formatting (v3.1.0 — Universal Inline Command Refactor)
# --------------------------------------------------------------------

MAX_TOOL_RESULT_CHARS = 4000  # ~1000 tokens
MAX_TOOL_RESULT_LINES = 100


def truncate_tool_result(content: str, max_chars: int = MAX_TOOL_RESULT_CHARS) -> str:
    """Truncate tool result to prevent token overflow."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n... [truncated]"


def format_tool_result_xml(
    tool_name: str,
    status: str,
    data: dict[str, Any] | None = None,
    error: str | None = None,
    command: str | None = None,
    truncate: bool = True,
) -> str:
    """
    Format tool result as XML for storage with role: "tools".

    This is the NEW universal format replacing markdown <details> contract.

    Output structure:
    <tool_result name="tool_name" status="ok|error">
        <command>/tool_name args...</command>
        <data>
            <key>value</key>
            ...
        </data>
        <error>error message</error>
    </tool_result>

    For LLM context in 2nd pass, this XML is clean and parseable.
    """
    lines = [f'<tool_result name="{_sanitize_xml_attribute(tool_name)}" status="{status}">']

    if command:
        lines.append(f"  <command>{sanitize_xml_value(command)}</command>")

    if status == "error" and error:
        lines.append(f"  <error>{sanitize_xml_value(error)}</error>")

    if data and status == "ok":
        lines.append("  <data>")
        for key, value in data.items():
            if isinstance(value, dict):
                # Nested dict — flatten with dot notation
                for nested_key, nested_val in value.items():
                    full_key = f"{key}.{nested_key}"
                    safe_val = sanitize_xml_value(str(nested_val))
                    if truncate:
                        safe_val = truncate_tool_result(safe_val)
                    lines.append(f"    <{full_key}>{safe_val}</{full_key}>")
            elif isinstance(value, list):
                # List — create multiple elements
                for i, item in enumerate(value[:20]):  # Limit to 20 items
                    safe_val = sanitize_xml_value(str(item))
                    if truncate:
                        safe_val = truncate_tool_result(safe_val)
                    lines.append(f"    <{key}>{safe_val}</{key}>")
                if len(value) > 20:
                    lines.append(f"    <{key}>... and {len(value) - 20} more</{key}>")
            else:
                safe_val = sanitize_xml_value(str(value))
                if truncate:
                    safe_val = truncate_tool_result(safe_val)
                lines.append(f"    <{key}>{safe_val}</{key}>")
        lines.append("  </data>")

    lines.append("</tool_result>")
    return "\n".join(lines)


# --------------------------------------------------------------------
# Dual-format result builder (v3.1.0 transitional)
# --------------------------------------------------------------------


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
    """Construct a successful tool result with BOTH markdown and XML formats.

    v3.1.0: Returns dual format for backward compatibility.
    - "markdown": Legacy <details> block (UI rendering)
    - "xml": New XML format (DB storage for 2nd pass)
    """
    return {
        "ok": True,
        "data": data,
        "markdown": build_tool_contract(tool_def, full_command, _flatten_lines(data), partner_name),
        "xml": format_tool_result_xml(
            tool_name=tool_def.name,
            status="ok",
            data=data,
            command=full_command,
        ),
    }


def error_result(
    message: str,
    tool_def: ToolDefinition,
    full_command: str,
    partner_name: str = "Yuzu",
) -> dict:
    """Construct an error tool result with BOTH markdown and XML formats.

    v3.1.0: Returns dual format for backward compatibility.
    """
    return {
        "ok": False,
        "error": message,
        "markdown": build_tool_contract(tool_def, full_command, [f"Error: {message}"], partner_name),
        "xml": format_tool_result_xml(
            tool_name=tool_def.name,
            status="error",
            error=message,
            command=full_command,
        ),
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
