#!/usr/bin/env python3
"""
Setup default MCP servers for Yuzu Companion
Run this to add common MCP servers to the database
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database

DEFAULT_MCP_SERVERS = [
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
        "command": "uvx",
        "args": ["mcp-server-fetch"],
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
]

def setup_mcp_servers():
    print("🍊 Setting up default MCP servers...")
    
    for server in DEFAULT_MCP_SERVERS:
        # Check if already exists
        existing = Database.get_mcp_server(name=server["name"])
        if existing:
            print(f"  ⏭️  {server['name']} already exists, skipping")
            continue
        
        # Create new server
        server_id = Database.create_mcp_server(
            name=server["name"],
            transport=server["transport"],
            command=server["command"],
            args=server["args"],
            url=None,
            env_vars=None
        )
        
        if server_id:
            print(f"  ✅ Added {server['name']}: {server['description']}")
        else:
            print(f"  ❌ Failed to add {server['name']}")
    
    print("\n📋 Current MCP servers:")
    servers = Database.list_mcp_servers()
    for s in servers:
        print(f"  - {s['name']}: {s['transport']} | active: {s['is_active']}")

if __name__ == "__main__":
    from database import init_db
    init_db()
    setup_mcp_servers()
