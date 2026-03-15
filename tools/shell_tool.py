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
            request_id = request.get("id")
            
            # Handle notifications (no id, no response needed)
            if method == "notifications/initialized":
                # This is a notification, no response needed
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
                    # Notification with unknown method, ignore
                    continue
            
            print(json.dumps(response), flush=True)
            
        except json.JSONDecodeError:
            pass


if __name__ == "__main__":
    main()
