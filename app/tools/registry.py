# FILE: app/tools/registry.py
# DESCRIPTION: Central tool registry — single source of truth for dispatch.
#
# Architecture:
#   - TOOL_DEFINITIONS: dict[name -> ToolDefinition] — canonical tools only
#   - TOOL_ALIAS_MAP: dict[alias -> canonical_name]
#   - _TOOL_MODULES: dict[name -> module] — lazy-loaded on first dispatch
#   - execute_tool(): validates arguments, calls tool.execute(), normalizes result
#   - get_tool_definitions(): returns canonical tool schemas for LLM tools[] array
#   - get_tools_by_role(): filters tools by role
#
# How to register a new tool:
#   1. Add TOOL_DEFINITION to the tool's module (e.g. image_generate.py)
#   2. Set aliases/category/execution_mode in the TOOL_DEFINITION if needed
#   3. Import it in _collect_definitions() below
#   4. The tool must have execute(arguments, session_id=None) -> dict

from typing import Any, Optional

from app.tools.schemas import error_result, normalize_tool_result

_TOOL_MODULES: dict[str, Any] = {}
_TOOL_DEFINITIONS: dict[str, Any] = {}
_TOOL_ALIAS_MAP: dict[str, str] = {}
_DEFINITIONS_INITIALIZED = False


def _register_definition(tool_def):
    canonical_name = tool_def.name
    _TOOL_DEFINITIONS[canonical_name] = tool_def
    _TOOL_ALIAS_MAP[canonical_name] = canonical_name

    for alias in getattr(tool_def, "aliases", []) or []:
        _TOOL_ALIAS_MAP[alias] = canonical_name


def _load_tool_module(tool_name: str):
    """Lazy-import a tool module by canonical name."""
    if tool_name not in _TOOL_MODULES:
        if tool_name == "image_generate":
            from app.tools import image_generate
            _TOOL_MODULES[tool_name] = image_generate
        elif tool_name == "http_request":
            from app.tools import http_request
            _TOOL_MODULES[tool_name] = http_request
        elif tool_name == "memory_store":
            from app.tools import memory_store
            _TOOL_MODULES[tool_name] = memory_store
        elif tool_name == "memory_search":
            from app.tools import memory_search
            _TOOL_MODULES[tool_name] = memory_search
        elif tool_name == "multimodal":
            from app.tools import multimodal
            _TOOL_MODULES[tool_name] = multimodal
        else:
            return None
    return _TOOL_MODULES.get(tool_name)


def _collect_definitions():
    """Lazily import and register all canonical tool definitions."""
    global _DEFINITIONS_INITIALIZED
    if _DEFINITIONS_INITIALIZED:
        return

    try:
        from app.tools import image_generate
        _register_definition(image_generate.TOOL_DEFINITION)
    except Exception as e:
        print(f"[registry] Failed to load image_generate definition: {e}")

    try:
        from app.tools import http_request
        _register_definition(http_request.TOOL_DEFINITION)
    except Exception as e:
        print(f"[registry] Failed to load http_request definition: {e}")

    try:
        from app.tools import memory_store
        _register_definition(memory_store.TOOL_DEFINITION)
    except Exception as e:
        print(f"[registry] Failed to load memory_store definition: {e}")

    try:
        from app.tools import memory_search
        _register_definition(memory_search.TOOL_DEFINITION)
    except Exception as e:
        print(f"[registry] Failed to load memory_search definition: {e}")

    _DEFINITIONS_INITIALIZED = True


def _resolve_tool_name(tool_name: str) -> str:
    _collect_definitions()
    return _TOOL_ALIAS_MAP.get(tool_name, tool_name)


# --------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------

def get_tool_definitions() -> list:
    """Return all canonical tool definitions for LLM tools[] array."""
    _collect_definitions()
    return [
        _TOOL_DEFINITIONS[name]
        for name in sorted(_TOOL_DEFINITIONS.keys())
    ]


def get_tool_definition(name: str):
    """Return a single tool definition by canonical name or alias."""
    _collect_definitions()
    canonical_name = _resolve_tool_name(name)
    return _TOOL_DEFINITIONS.get(canonical_name)


def get_tools_by_role(role: str) -> list:
    """Return all canonical tools that match the given role."""
    _collect_definitions()
    return [t for t in _TOOL_DEFINITIONS.values() if t.role == role]


def get_tool_role(tool_name: str) -> str:
    """Get the storage role for a tool name (for DB)."""
    tool_def = get_tool_definition(tool_name)
    if tool_def:
        return tool_def.role
    return f"{tool_name}_tools"


def is_terminal_tool(tool_name: str) -> bool:
    """Check if a tool is terminal (skips second LLM pass on success)."""
    tool_def = get_tool_definition(tool_name)
    if tool_def:
        return tool_def.is_terminal
    return False


# --------------------------------------------------------------------
# Legacy support
# --------------------------------------------------------------------

TOOL_ROLE_MAP = {
    "image_generate": "image_tools",
    "imagine": "image_tools",
    "request": "request_tools",
    "http_request": "request_tools",
    "memory_store": "memory_store_tools",
    "memory_search": "memory_search_tools",
}


def build_markdown_contract(
    tool_role: str,
    full_command: str,
    output_lines: list[str],
    partner_name: str = "Yuzu",
) -> str:
    """Build a markdown contract string.

    Note: New code should use schemas.build_tool_contract() instead.
    This function is kept for backward compatibility with existing tools.
    """
    from app.tools.schemas import ToolDefinition, build_tool_contract

    temp_def = ToolDefinition(name="", description="", role=tool_role)
    return build_tool_contract(temp_def, full_command, output_lines, partner_name)


# --------------------------------------------------------------------
# Main dispatch
# --------------------------------------------------------------------

def execute_tool(tool_name: str, arguments: dict, session_id: Optional[str] = None) -> dict:
    """Dispatch a tool call and return a structured result dict.

    This is the single source of truth for tool dispatch.
    All tool execution MUST go through this function.
    """
    _collect_definitions()

    canonical_name = _resolve_tool_name(tool_name)
    tool_def = _TOOL_DEFINITIONS.get(canonical_name)
    if not tool_def:
        return {
            "ok": False,
            "error": f"Unknown tool: {tool_name}",
            "markdown": build_markdown_contract(
                f"{tool_name}_tools",
                f"/{tool_name}",
                ["Error: Unknown tool. Available tools: " + ", ".join(sorted(_TOOL_DEFINITIONS.keys()))],
                "Yuzu",
            ),
            "meta": {"tool_name": tool_name, "canonical_name": None},
        }

    module = _load_tool_module(canonical_name)
    if not module:
        return error_result(
            f"Tool module unavailable: {canonical_name}",
            tool_def,
            f"/{canonical_name}",
            _get_partner_name(),
            meta={"tool_name": tool_name, "canonical_name": canonical_name},
        )

    validated_arguments, validation_errors = tool_def.validate_arguments(arguments)
    if validation_errors:
        return error_result(
            "Invalid tool arguments: " + "; ".join(validation_errors),
            tool_def,
            f"/{canonical_name}",
            _get_partner_name(),
            meta={
                "tool_name": tool_name,
                "canonical_name": canonical_name,
                "validation_errors": validation_errors,
            },
        )

    if tool_def.needs_session and "session_id" not in validated_arguments:
        validated_arguments["session_id"] = session_id

    full_command = _build_full_command(canonical_name, validated_arguments)

    try:
        result = module.execute(validated_arguments, session_id=session_id)
        return normalize_tool_result(
            result,
            tool_def,
            full_command,
            _get_partner_name(),
            meta={
                "tool_name": tool_name,
                "canonical_name": canonical_name,
            },
        )
    except Exception as e:
        print(f"[tool_error] {canonical_name}: {e}")
        return error_result(
            "Tool execution failed. Please try again later.",
            tool_def,
            full_command,
            _get_partner_name(),
            meta={
                "tool_name": tool_name,
                "canonical_name": canonical_name,
            },
        )


def _build_full_command(tool_name: str, arguments: dict[str, Any]) -> str:
    if not arguments:
        return f"/{tool_name}"

    parts = []
    for key, value in arguments.items():
        if key == "session_id":
            continue
        if isinstance(value, str):
            safe_value = value.replace('"', '\\"')
            parts.append(f'{key}="{safe_value}"')
        else:
            parts.append(f"{key}={value}")

    if parts:
        return f"/{tool_name} " + " ".join(parts)
    return f"/{tool_name}"


def _get_partner_name() -> str:
    """Get partner name from profile for error messages."""
    try:
        from app.database import Database
        profile = Database.get_profile() or {}
        return profile.get("partner_name", "Yuzu")
    except Exception:
        return "Yuzu"
