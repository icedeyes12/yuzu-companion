#!/usr/bin/env python3
"""
Update MCP server configurations to use locally installed packages
Run this after install_mcp_servers.sh
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database, init_db

def setup_local_mcp_servers():
    """Update MCP servers to use local npm packages instead of npx"""
    
    # Get MCP servers directory
    mcp_dir = os.path.expanduser("~/.mcp-servers")
    
    if not os.path.exists(mcp_dir):
        print(f"❌ MCP directory not found: {mcp_dir}")
        print("Run: bash scripts/install_mcp_servers.sh")
        return False
    
    # Check if packages are installed
    bin_dir = os.path.join(mcp_dir, "node_modules/.bin")
    if not os.path.exists(bin_dir):
        print(f"❌ No packages found in {mcp_dir}")
        print("Run: bash scripts/install_mcp_servers.sh")
        return False
    
    # Update MCP servers to use local paths
    servers = Database.list_mcp_servers()
    
    for server in servers:
        name = server['name']
        server_id = server['id']
        
        # Determine the correct binary path
        if name == 'filesystem':
            binary = 'mcp-server-filesystem'
        elif name == 'fetch':
            binary = 'mcp-server-fetch'
        elif name == 'sqlite':
            binary = 'mcp-server-sqlite'
        elif name == 'memory':
            binary = 'mcp-server-memory'
        else:
            continue
        
        binary_path = os.path.join(bin_dir, binary)
        
        if not os.path.exists(binary_path):
            print(f"⚠️  Binary not found: {binary_path}")
            continue
        
        # Update server config
        try:
            # Get current config
            current = Database.get_mcp_server(server_id=server_id)
            if not current:
                continue
            
            args = current.get('args', [])
            
            # Update to use node with full path
            new_command = 'node'
            new_args = [binary_path] + args
            
            Database.update_mcp_server(
                server_id=server_id,
                command=new_command,
                args=new_args
            )
            
            print(f"✓ Updated {name}: node {binary_path}")
            
        except Exception as e:
            print(f"❌ Failed to update {name}: {e}")
    
    print("\n✅ MCP servers configured for local use")
    print("Restart Yuzu Companion to apply changes")
    return True

if __name__ == "__main__":
    init_db()
    setup_local_mcp_servers()
