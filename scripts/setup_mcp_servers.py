#!/usr/bin/env python3
"""
Setup all MCP servers for Yuzu Companion
Run this after install_mcp_servers.sh
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database

ALL_SERVERS = [
    {
        "name": "filesystem",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/sdcard/Documents"],
        "description": "Access files on device storage",
    },
    {
        "name": "fetch",
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "mcp_server_fetch"],
        "description": "Fetch URLs and web content",
    },
    {
        "name": "sqlite",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "/data/data/com.termux/files/home/yuzu-companion/yuzu_core.db"],
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
        "args": ["-y", "@modelcontextprotocol/server-git"],
        "description": "Git repository operations",
    },
    {
        "name": "time",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-time"],
        "description": "Time and date utilities",
    },
]

def setup_mcp_servers():
    print("🍊 Setting up all MCP servers...")
    print("")
    
    for server in ALL_SERVERS:
        existing = Database.get_mcp_server(name=server["name"])
        if existing:
            print(f"  ⏭️  {server['name']} already exists")
            continue
        
        server_id = Database.create_mcp_server(
            name=server["name"],
            transport=server["transport"],
            command=server["command"],
            args=server["args"],
            url=None,
            env_vars=None
        )
        
        if server_id:
            print(f"  ✅ {server['name']}: {server['description']}")
        else:
            print(f"  ❌ Failed to add {server['name']}")
    
    print("")
    print("📋 All MCP servers:")
    servers = Database.list_mcp_servers()
    for s in servers:
        status = "🟢" if s['is_active'] else "🔴"
        cmd = s.get('command', 'N/A')
        print(f"  {status} {s['name']}: {s['transport']} | cmd: {cmd}")
    
    print("")
    print("Next: Restart Yuzu Companion to start MCP servers")

if __name__ == "__main__":
    from database import init_db
    init_db()
    setup_mcp_servers()
