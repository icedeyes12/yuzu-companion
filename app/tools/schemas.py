# FILE: app/tools/schemas.py
# DESCRIPTION: Standard tool definition schema for function calling.
# All tools MUST expose a TOOL_DEFINITION and implement execute(arguments, session_id=None).

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GenerateResult:
    text: str = ""
    tool_calls: list = field(default_factory=list)


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str = ""


@dataclass
class ToolParam:
    """A single parameter for a tool's execute() function."""
    name: str
    description: str
    type: str = "string"
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


@dataclass
class ToolDefinition:
    """Complete definition of a callable tool.

    This object is the single source of truth for:
    - The LLM's tools[] array (serialized to function-calling schema)
    - Dispatcher routing (tool_name -> module)
    - Role categorization for DB storage
    - Terminal/non-terminal classification for second LLM pass
    - Tool metadata for future skill/tool orchestration
    """

    name: str
    description: str
    role: str
    parameters: list[ToolParam] = field(default_factory=list)
    is_terminal: bool = False
    needs_session: bool = False
    category: str = "general"
    execution_mode: str = "atomic"
    aliases: list[str] = field(default_factory=list)
    returns_schema: dict[str, Any] | None = None
    safety_notes: str = ""

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
                    "additionalProperties": False,
                },
            },
        }

    def to_manifest(self) -> dict[str, Any]:
        """Serialize tool metadata for internal registries and future skills."""
        return {
            "name": self.name,
            "description": self.description,
            "role": self.role,
            "category": self.category,
            "execution_mode": self.execution_mode,
            "aliases": list(self.aliases),
            "is_terminal": self.is_terminal,
            "needs_session": self.needs_session,
            "parameters": [
                {
                    "name": p.name,
                    "description": p.description,
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                    "enum": p.enum,
                }
                for p in self.parameters
            ],
            "returns_schema": self.returns_schema,
            "safety_notes": self.safety_notes,
        }

    def validate_arguments(self, arguments: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
        """Validate and coerce incoming tool arguments."""
        incoming = dict(arguments or {})
        sanitized: dict[str, Any] = {}
        errors: list[str] = []

        param_map = {param.name: param for param in self.parameters}

        for param in self.parameters:
            if param.name in incoming:
                value = incoming[param.name]
            elif not param.required and param.default is not None:
                value = param.default
            elif param.required:
                errors.append(f"Missing required parameter: {param.name}")
                continue
            else:
                continue

            if value is None:
                if param.required:
                    errors.append(f"Parameter '{param.name}' cannot be null")
                continue

            coerced, coercion_error = _coerce_value(value, param.type)
            if coercion_error:
                errors.append(f"Parameter '{param.name}': {coercion_error}")
                continue

            if param.enum and coerced not in param.enum:
                errors.append(
                    f"Parameter '{param.name}' must be one of: {', '.join(map(str, param.enum))}"
                )
                continue

            sanitized[param.name] = coerced

        for key, value in incoming.items():
            if key not in param_map:
                sanitized[key] = value

        return sanitized, errors


@dataclass
class ToolContext:
    session_id: str | None = None
    partner_name: str = "Yuzu"
    source: str = "llm"
    tool_name: str | None = None
    raw_arguments: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    markdown: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "ok": self.ok,
            "markdown": self.markdown,
            "meta": self.meta,
        }
        if self.ok:
            result["data"] = self.data
        else:
            result["error"] = self.error or "Tool execution failed"
            result["data"] = self.data
        return result


# --------------------------------------------------------------------
# Tool result standard
# --------------------------------------------------------------------
# Every tool's execute() MUST return this shape:
#
#   {"ok": True,  "data": {...}, "markdown": "<details>...</details>", "meta": {...}}
#   {"ok": False, "error": "...", "markdown": "<details>...</details>", "meta": {...}}
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

    Returns a ``<details>`` block - the ONLY format stored in DB
    and rendered by the frontend.
    """
    formatted_output = "\n".join(f"> {line}" for line in output_lines)

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
    meta: dict[str, Any] | None = None,
) -> dict:
    """Construct a successful tool result."""
    return ToolResult(
        ok=True,
        data=data,
        markdown=build_tool_contract(tool_def, full_command, _flatten_lines(data), partner_name),
        meta=meta or {},
    ).to_dict()


def error_result(
    message: str,
    tool_def: ToolDefinition,
    full_command: str,
    partner_name: str = "Yuzu",
    meta: dict[str, Any] | None = None,
) -> dict:
    """Construct an error tool result."""
    return ToolResult(
        ok=False,
        error=message,
        markdown=build_tool_contract(tool_def, full_command, [f"Error: {message}"], partner_name),
        meta=meta or {},
    ).to_dict()


def normalize_tool_result(
    result: Any,
    tool_def: ToolDefinition,
    full_command: str,
    partner_name: str = "Yuzu",
    meta: dict[str, Any] | None = None,
) -> dict:
    """Normalize legacy or modern tool output into the standard result shape."""
    if isinstance(result, dict) and "ok" in result:
        normalized = dict(result)
        normalized.setdefault("meta", {})
        if meta:
            normalized["meta"] = {**normalized["meta"], **meta}
        if "markdown" not in normalized or not normalized["markdown"]:
            if normalized.get("ok"):
                normalized["markdown"] = build_tool_contract(
                    tool_def,
                    full_command,
                    _flatten_lines(normalized.get("data", {})),
                    partner_name,
                )
            else:
                normalized["markdown"] = build_tool_contract(
                    tool_def,
                    full_command,
                    [f"Error: {normalized.get('error', 'Tool execution failed')}"],
                    partner_name,
                )
        return normalized

    if isinstance(result, str) and result.strip().startswith("<details>"):
        normalized = {
            "ok": True,
            "data": {},
            "markdown": result,
            "meta": meta or {},
        }
        return normalized

    text = str(result)
    return ok_result(
        {"result": text},
        tool_def,
        full_command,
        partner_name,
        meta=meta,
    )


def _coerce_value(value: Any, expected_type: str) -> tuple[Any, str | None]:
    if expected_type == "string":
        if isinstance(value, str):
            return value.strip(), None
        return str(value), None

    if expected_type == "integer":
        if isinstance(value, bool):
            return value, "expected integer"
        if isinstance(value, int):
            return value, None
        try:
            return int(value), None
        except Exception:
            return value, "expected integer"

    if expected_type == "number":
        if isinstance(value, bool):
            return value, "expected number"
        if isinstance(value, (int, float)):
            return value, None
        try:
            return float(value), None
        except Exception:
            return value, "expected number"

    if expected_type == "boolean":
        if isinstance(value, bool):
            return value, None
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True, None
            if lowered in {"false", "0", "no", "n"}:
                return False, None
        return value, "expected boolean"

    if expected_type == "array":
        if isinstance(value, list):
            return value, None
        return value, "expected array"

    if expected_type == "object":
        if isinstance(value, dict):
            return value, None
        return value, "expected object"

    return value, None


def _flatten_lines(data: dict) -> list[str]:
    """Flatten a result dict into displayable lines."""
    lines = []
    for key, value in data.items():
        if isinstance(value, str) and value.startswith("<"):
            lines.append(value)
        else:
            lines.append(f"{key}: {value}")
    return lines
