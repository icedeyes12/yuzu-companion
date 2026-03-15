#!/usr/bin/env python3
"""
MCP Git Server - Execute git commands
Lightweight wrapper around git CLI
"""

import subprocess
import json
import sys
import os

# Default repository path (can be overridden via args)
REPO_PATH = "/home/workspace/yuzu-companion"


def handle_initialize():
    return {
        "jsonrpc": "2.0",
        "id": "init",
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "serverInfo": {
                "name": "git-mcp",
                "version": "1.0.0"
            }
        }
    }


def handle_tools_list():
    return {
        "jsonrpc": "2.0",
        "id": "tools_list",
        "result": {
            "tools": [
                {
                    "name": "git_status",
                    "description": "Show working tree status (git status)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Repository path (optional, defaults to configured path)"
                            }
                        }
                    }
                },
                {
                    "name": "git_log",
                    "description": "Show commit history (git log --oneline -n 10)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "n": {
                                "type": "integer",
                                "description": "Number of commits to show",
                                "default": 10
                            },
                            "path": {
                                "type": "string",
                                "description": "Repository path (optional)"
                            }
                        }
                    }
                },
                {
                    "name": "git_diff",
                    "description": "Show changes between commits or working tree (git diff)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "commit1": {
                                "type": "string",
                                "description": "First commit/branch (optional)"
                            },
                            "commit2": {
                                "type": "string",
                                "description": "Second commit/branch (optional)"
                            },
                            "path": {
                                "type": "string",
                                "description": "Repository path (optional)"
                            }
                        }
                    }
                },
                {
                    "name": "git_branch",
                    "description": "List branches (git branch -a)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Repository path (optional)"
                            }
                        }
                    }
                },
                {
                    "name": "git_show",
                    "description": "Show commit details (git show)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "commit": {
                                "type": "string",
                                "description": "Commit hash or ref",
                                "default": "HEAD"
                            },
                            "path": {
                                "type": "string",
                                "description": "Repository path (optional)"
                            }
                        }
                    }
                }
            ]
        }
    }


def run_git_command(args, cwd=None):
    """Run a git command and return result"""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd or REPO_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
                }
            ]
        }
    except Exception as e:
        return {
            "content": [
                {"type": "text", "text": f"Error: {str(e)}"}
            ],
            "isError": True
        }


def handle_tool_call(params):
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    path = arguments.get("path", REPO_PATH)
    
    if tool_name == "git_status":
        return run_git_command(["status"], cwd=path)
    
    elif tool_name == "git_log":
        n = arguments.get("n", 10)
        return run_git_command(["log", "--oneline", "-n", str(n)], cwd=path)
    
    elif tool_name == "git_diff":
        commit1 = arguments.get("commit1")
        commit2 = arguments.get("commit2")
        if commit1 and commit2:
            return run_git_command(["diff", commit1, commit2], cwd=path)
        elif commit1:
            return run_git_command(["diff", commit1], cwd=path)
        else:
            return run_git_command(["diff"], cwd=path)
    
    elif tool_name == "git_branch":
        return run_git_command(["branch", "-a"], cwd=path)
    
    elif tool_name == "git_show":
        commit = arguments.get("commit", "HEAD")
        return run_git_command(["show", "--stat", commit], cwd=path)
    
    return {
        "content": [
            {"type": "text", "text": f"Unknown git tool: {tool_name}"}
        ],
        "isError": True
    }


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            request = json.loads(line)
            method = request.get("method")
            request_id = request.get("id")
            
            # Handle notifications (no id, no response needed)
            if method == "notifications/initialized":
                continue
            
            # Handle requests (have id, need response)
            if method == "initialize":
                response = handle_initialize()
                response["id"] = request_id
            elif method == "tools/list":
                response = handle_tools_list()
                response["id"] = request_id
            elif method == "tools/call":
                result_data = handle_tool_call(request.get("params", {}))
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result_data
                }
            else:
                # Only return error for requests (with id)
                if request_id is not None:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"}
                    }
                else:
                    continue
            
            print(json.dumps(response), flush=True)
            
        except json.JSONDecodeError:
            pass


if __name__ == "__main__":
    main()
