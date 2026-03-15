#!/usr/bin/env python3
"""
Setup all MCP servers for Yuzu Companion
Run this after install_mcp_servers.sh
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database

# Get the project root directory
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = os.path.expanduser("~/workspace") if os.path.exists(os.path.expanduser("~/workspace")) else "/home/workspace"

ALL_SERVERS = [
    {
        "name": "filesystem",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/workspace"],
        "description": "Access files on workspace storage",
    },
    {
        "name": "fetch",
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "description": "Fetch URLs and web content",
    },
    {
        "name": "memory",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "description": "Persistent knowledge graph memory",
    },
    {
        "name": "shell",
        "transport": "stdio",
        "command": "python3",
        "args": ["tools/shell_tool.py"],
        "description": "Execute shell commands (WARNING: High risk)",
    },
]

def setup_mcp_servers():
    """Create all MCP server configurations."""
    print("Setting up MCP servers...")
    print(f"Project directory: {PROJECT_DIR}")
    print(f"Workspace directory: {WORKSPACE_DIR}")
    
    for server in ALL_SERVERS:
        try:
            server_id = Database.create_mcp_server(
                name=server["name"],
                transport=server["transport"],
                command=server["command"],
                args=server["args"],
                url=server.get("url"),
                env_vars=server.get("env_vars", {}),
            )
            if server_id:
                print(f"  ✅ {server['name']}: Created")
            else:
                print(f"  ℹ️  {server['name']}: Already exists")
        except Exception as e:
            print(f"  ⚠️  {server['name']}: Error - {e}")
    
    print("MCP server setup complete!")

if __name__ == "__main__":
    setup_mcp_servers()
