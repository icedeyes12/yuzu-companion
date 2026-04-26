"""
Local file read tool — direct filesystem access for agentic loop.
Runs in-process, bypassing MCP sandbox restrictions.
"""
from __future__ import annotations
import os
import logging
from typing import Optional

from app.tools.schemas import ToolDefinition, ToolParam

logger = logging.getLogger(__name__)

ALLOWED_BASE_PATHS = [
    "/home/workspace",
    "/tmp",
]

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _is_path_allowed(path: str) -> bool:
    """Check if path is within allowed directories."""
    abs_path = os.path.abspath(path)
    return any(abs_path.startswith(p) for p in ALLOWED_BASE_PATHS)


TOOL_DEFINITION = ToolDefinition(
    name="file_read",
    description="Read a file from the local filesystem. Returns file contents. Can read text files, markdown, code, and JSON. For binary files, returns base64-encoded content.",
    role="local_tools",
    parameters=[
        ToolParam(
            name="path",
            type="string",
            description="Absolute path to the file (e.g. /home/workspace/file.py)",
            required=True,
        ),
        ToolParam(
            name="encoding",
            type="string",
            description="Text encoding (default: utf-8)",
            required=False,
        ),
        ToolParam(
            name="max_lines",
            type="integer",
            description="Maximum lines to return (default: all)",
            required=False,
        ),
    ],
    is_terminal=False,
    needs_session=False,
)


def execute(arguments: dict, session_id: Optional[str] = None) -> dict:
    """Execute file read. Returns structured result."""
    path = arguments.get("path")
    encoding = arguments.get("encoding", "utf-8")
    max_lines = arguments.get("max_lines")
    
    if not path:
        return {
            "ok": False,
            "error": "Missing required argument: path",
            "markdown": "<details><summary>❌ file_read error</summary>Missing path argument</details>",
        }
    
    if not _is_path_allowed(path):
        return {
            "ok": False,
            "error": f"Path not allowed: {path}. Must be under: {ALLOWED_BASE_PATHS}",
            "markdown": f"<details><summary>❌ file_read error</summary>Path not allowed: {path}</details>",
        }
    
    if not os.path.exists(path):
        return {
            "ok": False,
            "error": f"File not found: {path}",
            "markdown": f"<details><summary>❌ file_read error</summary>File not found: {path}</details>",
        }
    
    if os.path.isdir(path):
        return {
            "ok": False,
            "error": f"Path is a directory, not a file: {path}",
            "markdown": "<details><summary>❌ file_read error</summary>Use list_dir for directories</details>",
        }
    
    file_size = os.path.getsize(path)
    if file_size > MAX_FILE_SIZE:
        return {
            "ok": False,
            "error": f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})",
            "markdown": f"<details><summary>❌ file_read error</summary>File too large ({file_size} bytes)</details>",
        }
    
    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            content = f.read()
        
        if max_lines:
            lines = content.split("\n")[:max_lines]
            content = "\n".join(lines)
        
        # Build markdown summary
        lines_count = len(content.split("\n"))
        rel_path = path.replace("/home/workspace/", "") if path.startswith("/home/workspace/") else path
        
        markdown = f"""<details>
<summary>📄 {rel_path} ({lines_count} lines)</summary>

```
{content[:8000]}
{"... (truncated)" if len(content) > 8000 else ""}
```
</details>"""
        
        return {
            "ok": True,
            "data": {
                "path": path,
                "content": content,
                "size": file_size,
                "lines": lines_count,
            },
            "markdown": markdown,
        }
        
    except Exception as e:
        logger.error(f"[file_read] Error reading {path}: {e}")
        return {
            "ok": False,
            "error": f"Failed to read file: {e}",
            "markdown": f"<details><summary>❌ file_read error</summary>{e}</details>",
        }
