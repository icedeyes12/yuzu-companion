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
        "args": ["-y", "@modelcontextprotocol/server-filesystem", WORKSPACE_DIR],
        "description": "Access files on device storage",
    },
    {
        "name": "fetch",
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "description": "Fetch URLs and web content",
    },
    {
        "name": "sqlite",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", os.path.join(PROJECT_DIR, "/yuzu_core.db")],
        "description": "Query SQLite databases",
    },
    {
        "name": "memory",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "description": "Persistent key-value storage",
    },
    {
        "name": "git",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-git", PROJECT_DIR],
        "description": "Git repository operations",
    },
    {
        "name": "time",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-time"],
        "description": "Time and date utilities",
    },
    {
        "name": "weather",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-fetch"],  # Using fetch as weather API caller
        "description": "Weather information (requires manual configuration)",
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
