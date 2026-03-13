#!/usr/bin/env python3
"""
Add git and time MCP servers to Yuzu Companion
"""
import sys
sys.path.insert(0, '/home/workspace/yuzu-companion')

from database import Database, init_db

def add_git_time_servers():
    """Add git and time MCP servers"""
    
    servers = [
        {
            "name": "git",
            "transport": "stdio",
            "command": "uvx",  # or: python -m mcp_server_git
            "args": ["mcp-server-git"],
            "description": "Git operations - repo status, branches, commits"
        },
        {
            "name": "time", 
            "transport": "stdio",
            "command": "uvx",
            "args": ["mcp-server-time"],
            "description": "Time utilities - current time, timezone conversion"
        }
    ]
    
    added = 0
    for server in servers:
        existing = Database.get_mcp_server(name=server["name"])
        if not existing:
            server_id = Database.create_mcp_server(
                name=server["name"],
                transport=server["transport"],
                command=server["command"],
                args=server["args"]
            )
            if server_id:
                print(f"✅ Added {server['name']}: {server['description']}")
                added += 1
            else:
                print(f"❌ Failed to add {server['name']}")
        else:
            print(f"⚠️  {server['name']} already exists")
    
    print(f"\n🎉 Added {added} new MCP servers")
    print("Install with: uv pip install mcp-server-git mcp-server-time")
    print("   or: pip install mcp-server-git mcp-server-time")

if __name__ == "__main__":
    init_db()
    add_git_time_servers()
