#!/usr/bin/env python3
"""
Diagnose MCP server installation and configuration
Usage: python scripts/diagnose_mcp.py
"""

import sys
import os
import subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database, init_db

def check_command(cmd):
    """Check if a command is available"""
    try:
        result = subprocess.run(['which', cmd], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def diagnose():
    print("🔍 MCP Server Diagnostics")
    print("=" * 50)
    
    # Check required tools
    print("\n📦 Required Tools:")
    tools = {
        'npx': 'Node.js package runner',
        'node': 'Node.js runtime',
        'uvx': 'Python package runner (uv)',
        'npm': 'Node.js package manager'
    }
    
    for tool, desc in tools.items():
        status = "✅" if check_command(tool) else "❌"
        print(f"  {status} {tool}: {desc}")
    
    # Check database
    print("\n📋 Database Status:")
    init_db()
    servers = Database.list_mcp_servers()
    
    if not servers:
        print("  ⚠️  No MCP servers configured")
        print("     Run: python scripts/setup_mcp_servers.py")
    else:
        print(f"  ✅ {len(servers)} server(s) configured:")
        for s in servers:
            print(f"     - {s['name']} ({s['transport']}) - {'active' if s['is_active'] else 'inactive'}")
    
    print("\n🔧 Quick Fixes:")
    print("  1. Install packages:  bash scripts/install_mcp_servers.sh")
    print("  2. Configure:         python scripts/setup_mcp_servers.py")
    print("  3. Restart Yuzu:      python web.py")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    diagnose()
