"""
Local directory listing tool — list files in a directory.
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


def _is_path_allowed(path: str) -> bool:
    abs_path = os.path.abspath(path)
    return any(abs_path.startswith(p) for p in ALLOWED_BASE_PATHS)


TOOL_DEFINITION = ToolDefinition(
    name="list_dir",
    description="List files and directories in a path. Returns a tree-style listing of files and folders.",
    role="local_tools",
    parameters=[
        ToolParam(
            name="path",
            type="string",
            description="Absolute path to directory (e.g. /home/workspace)",
            required=True,
        ),
        ToolParam(
            name="depth",
            type="integer",
            description="Maximum depth to traverse (default: 2, max: 5)",
            required=False,
        ),
    ],
    is_terminal=False,
    needs_session=False,
)


def _list_tree(path: str, prefix: str = "", depth: int = 2, max_depth: int = 5) -> list[str]:
    """Recursively list directory tree."""
    if depth <= 0 or depth > max_depth:
        return []
    
    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        return [f"{prefix}❌ Permission denied"]
    
    lines = []
    dirs = []
    files = []
    
    for e in entries:
        if e.startswith(".") or e.startswith("__"):
            continue
        full = os.path.join(path, e)
        if os.path.isdir(full):
            dirs.append(e)
        else:
            files.append(e)
    
    for d in dirs[:20]:
        full = os.path.join(path, d)
        lines.append(f"{prefix}📁 {d}/")
        if depth > 1:
            lines.extend(_list_tree(full, prefix + "  ", depth - 1, max_depth))
    
    for f in files[:30]:
        size = os.path.getsize(os.path.join(path, f))
        if size > 1024 * 1024:
            size_str = f"{size // (1024*1024)}MB"
        elif size > 1024:
            size_str = f"{size // 1024}KB"
        else:
            size_str = f"{size}B"
        lines.append(f"{prefix}📄 {f} ({size_str})")
    
    if len(dirs) > 20:
        lines.append(f"{prefix}... and {len(dirs) - 20} more directories")
    if len(files) > 30:
        lines.append(f"{prefix}... and {len(files) - 30} more files")
    
    return lines


def execute(arguments: dict, session_id: Optional[str] = None) -> dict:
    """Execute directory listing."""
    path = arguments.get("path", "/home/workspace")
    depth = min(arguments.get("depth", 2), 5)
    
    if not _is_path_allowed(path):
        return {
            "ok": False,
            "error": f"Path not allowed: {path}",
            "markdown": "<details><summary>❌ list_dir error</summary>Path not allowed</details>",
        }
    
    if not os.path.exists(path):
        return {
            "ok": False,
            "error": f"Path not found: {path}",
            "markdown": "<details><summary>❌ list_dir error</summary>Path not found</details>",
        }
    
    if not os.path.isdir(path):
        return {
            "ok": False,
            "error": f"Not a directory: {path}",
            "markdown": "<details><summary>❌ list_dir error</summary>Use file_read for files</details>",
        }
    
    try:
        lines = _list_tree(path, depth=depth)
        rel_path = path.replace("/home/workspace/", "~/") if path.startswith("/home/workspace") else path
        
        markdown = f"""<details>
<summary>📁 {rel_path}</summary>

```
{chr(10).join(lines[:100])}
{"... (truncated)" if len(lines) > 100 else ""}
```
</details>"""
        
        return {
            "ok": True,
            "data": {
                "path": path,
                "entries": lines,
                "count": len(lines),
            },
            "markdown": markdown,
        }
        
    except Exception as e:
        logger.error(f"[list_dir] Error: {e}")
        return {
            "ok": False,
            "error": str(e),
            "markdown": f"<details><summary>❌ list_dir error</summary>{e}</details>",
        }
