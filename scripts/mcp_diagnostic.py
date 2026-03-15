#!/usr/bin/env python3
"""
MCP Server Diagnostic Tool
Tests all MCP servers and reports their health status
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from tools.orchestration.mcp_manager import get_mcp_manager, ServerStatus
import json


def test_server_tools(server_name, verbose=False):
    """Test tool discovery for a specific server."""
    mcp = get_mcp_manager()
    
    print(f"\n🔍 Testing {server_name}...")
    
    # Check if server exists in DB
    config = Database.get_mcp_server(name=server_name)
    if not config:
        print(f"   ❌ Server not found in database")
        return False
    
    if verbose:
        print(f"   Config: {config['command']} {' '.join(config['args'])}")
    
    # Try to start the server
    success = mcp.start_server(server_name)
    if not success:
        status = mcp.get_server_status(server_name)
        print(f"   ❌ Failed to start: {status.get('last_error', 'Unknown error')}")
        return False
    
    # Check status
    status = mcp.get_server_status(server_name)
    print(f"   ✅ Server running")
    
    # Check tools
    tools = status.get('tools', [])
    if tools:
        print(f"   ✅ {len(tools)} tools discovered:")
        for tool in tools[:5]:  # Show first 5
            print(f"      • {tool['name']}")
        if len(tools) > 5:
            print(f"      ... and {len(tools) - 5} more")
        return True
    else:
        print(f"   ⚠️  No tools discovered (server running but no tools found)")
        return False


def run_full_diagnostic():
    """Run diagnostic on all MCP servers."""
    print("=" * 60)
    print("🔧 MCP Server Diagnostic Tool")
    print("=" * 60)
    
    # Get all servers from DB
    servers = Database.list_mcp_servers()
    
    if not servers:
        print("\n⚠️  No MCP servers configured!")
        print("   Run: python scripts/setup_mcp_servers.py")
        return
    
    print(f"\n📊 Found {len(servers)} MCP server(s) in database")
    
    results = {
        "passed": [],
        "failed": [],
        "no_tools": []
    }
    
    for server in servers:
        name = server['name']
        try:
            success = test_server_tools(name, verbose=True)
            if success:
                results["passed"].append(name)
            else:
                status = get_mcp_manager().get_server_status(name)
                if status.get('status') == 'running':
                    results["no_tools"].append(name)
                else:
                    results["failed"].append(name)
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results["failed"].append(name)
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 Diagnostic Summary")
    print("=" * 60)
    
    print(f"\n✅ Working ({len(results['passed'])}):")
    for name in results["passed"]:
        print(f"   • {name}")
    
    if results["no_tools"]:
        print(f"\n⚠️  Running but no tools ({len(results['no_tools'])}):")
        for name in results["no_tools"]:
            print(f"   • {name}")
    
    if results["failed"]:
        print(f"\n❌ Failed to start ({len(results['failed'])}):")
        for name in results["failed"]:
            print(f"   • {name}")
    
    # Recommendations
    print("\n💡 Recommendations:")
    if results["failed"]:
        print("   • Check that npx/uvx commands are available: npx --version")
        print("   • For Python-based servers, ensure packages are installed")
        print("   • Check server configurations match your environment")
    
    if results["no_tools"]:
        print("   • Servers running but tool discovery failed - check timeout settings")
        print("   • Some servers may need manual tool discovery trigger")
    
    if not results["passed"]:
        print("   • No working MCP servers - install MCP servers first:")
        print("     npm install -g @modelcontextprotocol/server-memory")
        print("     npm install -g @modelcontextprotocol/server-filesystem")
        print("     etc.")


def list_available_tools():
    """List all available tools from all running servers."""
    print("\n📦 Available MCP Tools:")
    print("-" * 60)
    
    mcp = get_mcp_manager()
    tools = mcp.get_all_tools()
    
    if not tools:
        print("   No tools available. Start some MCP servers first!")
        return
    
    # Group by server
    by_server = {}
    for tool in tools:
        server = tool.server_name
        if server not in by_server:
            by_server[server] = []
        by_server[server].append(tool)
    
    for server, server_tools in by_server.items():
        print(f"\n🔌 {server} ({len(server_tools)} tools):")
        for tool in server_tools:
            desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
            print(f"   • {tool.name}: {desc}")


def update_server_paths():
    """Update server paths to match current environment."""
    print("\n🔄 Updating server paths...")
    
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace_dir = "/home/workspace"
    
    updates = {
        "filesystem": {"args": ["-y", "@modelcontextprotocol/server-filesystem", workspace_dir]},
        "sqlite": {"args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", os.path.join(project_dir, "yuzu_core.db")]},
        "git": {"args": ["-y", "@modelcontextprotocol/server-git", project_dir]},
    }
    
    for name, new_config in updates.items():
        server = Database.get_mcp_server(name=name)
        if server:
            Database.update_mcp_server(server["id"], args=new_config["args"])
            print(f"   ✅ Updated {name} path")
        else:
            print(f"   ℹ️  {name} not found (will be created on setup)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Server Diagnostic Tool")
    parser.add_argument("--test", help="Test a specific server by name")
    parser.add_argument("--list", action="store_true", help="List all available tools")
    parser.add_argument("--update-paths", action="store_true", help="Update server paths for current environment")
    args = parser.parse_args()
    
    if args.test:
        test_server_tools(args.test, verbose=True)
    elif args.list:
        # Start all servers first
        mcp = get_mcp_manager()
        for server in Database.list_mcp_servers(active_only=True):
            try:
                mcp.start_server(server["name"])
            except:
                pass
        list_available_tools()
    elif args.update_paths:
        update_server_paths()
    else:
        run_full_diagnostic()
