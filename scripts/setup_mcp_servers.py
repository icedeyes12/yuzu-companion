#!/usr/bin/env python3
"""
Setup MCP servers for Yuzu Companion
Run this after install_mcp_servers.sh
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database

# Core servers (always enabled)
CORE_SERVERS = [
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
        "args": ["-m", "mcp_server_fetch"],  # pip installed
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
<<<<<<< HEAD
]

# Optional servers (uncomment to enable)
OPTIONAL_SERVERS = [
    # {
    #     "name": "github",
    #     "transport": "stdio",
    #     "command": "npx",
    #     "args": ["-y", "@modelcontextprotocol/server-github"],
    #     "description": "GitHub API access (needs GITHUB_TOKEN env var)",
    # },
    # {
    #     "name": "git",
    #     "transport": "stdio",
    #     "command": "python",
    #     "args": ["-m", "mcp_server_git"],
    #     "description": "Git operations",
    # },
    # {
    #     "name": "time",
    #     "transport": "stdio",
    #     "command": "python",
    #     "args": ["-m", "mcp_server_time"],
    #     "description": "Time and date utilities",
    # },
=======
    
    # ============================================
    # OPTIONAL SERVERS - Uncomment to enable
    # ============================================
    
    Git support
    {
        "name": "git",
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-git", "--repository", "/path/to/repo"],
        "description": "Git repository operations",
    },
    
    Time utilities
    {
        "name": "time",
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-time"],
        "description": "Time and date utilities",
    },
    
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
>>>>>>> a95bf42 (a)
    # {
    #     "name": "shell",
    #     "transport": "stdio",
    #     "command": "python3",
    #     "args": ["-c", "import subprocess,json,sys; [subprocess.run(json.loads(l)['params']['arguments']['command'], shell=True, stdout=sys.stdout, stderr=sys.stderr) for l in sys.stdin if json.loads(l).get('method')=='tools/call']"],
    #     "description": "⚠️ DANGEROUS: Execute shell commands",
    # },
]

def setup_mcp_servers():
    print("🍊 Setting up MCP servers...")
    print("")
    
    # Add core servers
    print("📦 Core servers:")
    for server in CORE_SERVERS:
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
    
    # Show optional servers
    if OPTIONAL_SERVERS:
        print("")
        print("🔧 Optional servers (edit setup_mcp_servers.py to enable):")
        for server in OPTIONAL_SERVERS:
            print(f"  # {server['name']}: {server['description']}")
    
    # List all
    print("")
    print("📋 Current MCP servers:")
    servers = Database.list_mcp_servers()
    for s in servers:
        status = "🟢" if s['is_active'] else "🔴"
        print(f"  {status} {s['name']}: {s['transport']} | cmd: {s.get('command', 'N/A')}")
    
    print("")
    print("Next: Restart Yuzu Companion to start MCP servers")

if __name__ == "__main__":
    from database import init_db
    init_db()
    setup_mcp_servers()
