import json
from tools import web_search, weather, memory_search, image_generate, image_analyze
from tools import memory_sql
from tools import http_request


_TOOLS = {
    "web_search": web_search,
    "weather": weather,
    "memory_search": memory_search,
    "memory_sql": memory_sql,
    "image_generate": image_generate,
    "image_analyze": image_analyze,
    "http_request": http_request
}


def get_tool_schemas():
    """Return list of tool schemas in OpenRouter format.
    
    http_request is excluded — it is a backend-only tool executed via
    the /request command and must never be injected into provider payloads.
    """
    return [mod.SCHEMA for name, mod in _TOOLS.items() if name != "http_request"]


def execute_tool(tool_name, arguments, session_id=None):
    """Dispatch a tool call and return the result string."""
    if tool_name not in _TOOLS:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    module = _TOOLS[tool_name]
    try:
        result = module.execute(arguments, session_id=session_id)
        return result
    except Exception as e:
        print(f"[tool_error] {tool_name}: {e}")
        return json.dumps({"error": f"Tool {tool_name} failed: {str(e)}"})
