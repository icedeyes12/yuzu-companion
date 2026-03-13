#!/usr/bin/env python3
"""
Setup default MCP servers for Yuzu Companion
Run this to add common MCP servers to the database

Usage: python scripts/setup_mcp_servers.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database

# ============================================
# DEFAULT MCP SERVERS
# Edit this list to add/remove servers
# ============================================
DEFAULT_MCP_SERVERS = [
    # Core servers (recommended)
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
        "args": ["-y", "@modelcontextprotocol/server-sqlite", 
                  "--db-path", "/data/data/com.termux/files/home/yuzu-companion/yuzu_core.db"],
        "description": "Query SQLite databases",
    },
    {
        "name": "memory",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "description": "Persistent key-value storage",
    },
    
    # ============================================
    # OPTIONAL SERVERS - Uncomment to enable
    # ============================================
    
    # Git support
    # {
    #     "name": "git",
    #     "transport": "stdio",
    #     "command": "uvx",
    #     "args": ["mcp-server-git", "--repository", "/path/to/repo"],
    #     "description": "Git repository operations",
    # },
    
    # Time utilities
    # {
    #     "name": "time",
    #     "transport": "stdio",
    #     "command": "uvx",
    #     "args": ["mcp-server-time"],
    #     "description": "Time and date utilities",
    # },
    
    # Puppeteer browser automation
    # {
    #     "name": "puppeteer",
    #     "transport": "stdio",
    #     "command": "npx",
    #     "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
    #     "description": "Browser automation and screenshots",
    # },
    
    # ============================================
    # DANGER ZONE - HIGH RISK
    # ============================================
    
    # ⚠️ Shell access - NO CONFIRMATION
    # Can delete files, install malware, exfiltrate data
    # {
    #     "name": "shell",
    #     "transport": "stdio",
    #     "command": "uvx",
    #     "args": ["mcp-shell"],
    #     "description": "⚠️ Shell command execution WITHOUT confirmation",
    # },
]

def setup_mcp_servers():
    print("🍊 Setting up default MCP servers...")
    print("=" * 50)
    
    added = 0
    skipped = 0
    
    for server in DEFAULT_MCP_SERVERS:
        existing = Database.get_mcp_server(name=server["name"])
        if existing:
            print(f"  ⏭️  {server['name']}: already exists")
            skipped += 1
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
            added += 1
        else:
            print(f"  ❌ {server['name']}: failed")
    
    print("=" * 50)
    print(f"\n📊 Summary: {added} added, {skipped} skipped")
    print("\n📋 Current MCP servers:")
    servers = Database.list_mcp_servers()
    for s in servers:
        status = "🟢" if s['is_active'] else "🔴"
        print(f"  {status} {s['name']}: {s['transport']}")
    
    print("\n💡 To add more servers, edit this file and uncomment optional servers")
    print("   Then run: python scripts/setup_mcp_servers.py")

if __name__ == "__main__":
    from database import init_db
    init_db()
    setup_mcp_servers()
