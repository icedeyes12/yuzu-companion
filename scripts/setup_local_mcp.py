#!/usr/bin/env python3
"""
Update MCP server configurations to use locally installed packages
Run this after install_mcp_servers.sh
"""

import sys
import os
import glob

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database, init_db

# Map of server names to binary names
BINARY_NAMES = {
    'mcp-server-filesystem': 'mcp-server-filesystem',
    'mcp-server-fetch': 'mcp-server-fetch',
    'mcp-server-sqlite': 'mcp-server-sqlite',
    'mcp-server-memory': 'mcp-server-memory'
}

def find_mcp_binary(bin_dir, name):
    try:
        # Try to find with glob
        pattern = os.path.join(bin_dir, f'mcp-server-{name}*')
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    except Exception as e:
        print(f"Error finding binary: {e}")
    return None

def setup_local_mcp_servers():
    """Update MCP servers to use local npm packages instead of npx"""
    
    # Get MCP servers directory
    mcp_dir = os.path.expanduser("~/.mcp-servers")
    bin_dir = os.path.join(mcp_dir, "node_modules/.bin")
    
    if not os.path.exists(bin_dir):
        print(f"❌ MCP directory not found: {bin_dir}")
        print("Run: bash scripts/install_mcp_servers.sh")
        return False
    
    # List available binaries
    available_bins = []
    if os.path.exists(bin_dir):
        available_bins = os.listdir(bin_dir)
        print(f"   Available binaries: {available_bins}")
    
    updated = 0
    # Update MCP servers to use local paths
    servers = Database.list_mcp_servers()
    
    for server in servers:
        server_id = server['id']
        name = server['name']
        
        # Find the correct binary
        binary_name = BINARY_NAMES.get(name, f'mcp-server-{name}')
        binary_path = os.path.join(bin_dir, binary_name)
        
        # Check if binary exists
        if not os.path.exists(binary_path):
            # Try to find with glob
            found = find_mcp_binary(bin_dir, name)
            if found:
                binary_path = found
            else:
                print(f"⚠️  Binary not found for {name}")
                continue
        
        # Update server config
        new_command = f'node {binary_path}'
        Database.update_mcp_server(
            server_id,
            command='node',
            args=[binary_path]
        )
        print(f"✓ Updated {name}: {new_command}")
        updated += 1
    
    print(f"\n✅ {updated} MCP servers configured for local use")
    print("Restart Yuzu Companion to apply changes")
    return True

if __name__ == "__main__":
    init_db()
    setup_local_mcp_servers()
