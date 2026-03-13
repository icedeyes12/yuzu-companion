#!/usr/bin/env python3
"""
MCP Shell Server - Execute shell commands
WARNING: HIGH RISK - Can execute ANY command
"""

import subprocess
import json
import sys


def handle_initialize():
    return {
        "jsonrpc": "2.0",
        "id": "init",
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "serverInfo": {
                "name": "shell-mcp",
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
                    "name": "execute_command",
                    "description": "Execute a shell command",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "Command to execute"
                            }
                        },
                        "required": ["command"]
                    }
                }
            ]
        }
    }


def handle_tool_call(params):
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    if tool_name == "execute_command":
        command = arguments.get("command", "")
        try:
            result = subprocess.run(
                command,
                shell=True,
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
    
    return {"content": [{"type": "text", "text": "Unknown tool"}], "isError": True}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            request = json.loads(line)
            method = request.get("method")
            
            if method == "initialize":
                response = handle_initialize()
            elif method == "tools/list":
                response = handle_tools_list()
            elif method == "tools/call":
                response = handle_tool_call(request.get("params", {}))
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
            
            print(json.dumps(response), flush=True)
            
        except json.JSONDecodeError:
            pass


if __name__ == "__main__":
    main()
