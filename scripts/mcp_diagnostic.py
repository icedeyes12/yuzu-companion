#!/usr/bin/env python3
"""
MCP Diagnostic Script for Yuzu Companion

Tests Zo MCP server connectivity and lists available tools.

Usage:
    python scripts/mcp_diagnostic.py
    python scripts/mcp_diagnostic.py --token YOUR_TOKEN

Environment:
    ZO_ACCESS_TOKEN - MCP access token from Zo Settings > Advanced
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run_diagnostic(token: str | None = None) -> None:
    """Run MCP diagnostic checks."""
    from app.mcp.client import MCPClient
    
    print("=" * 60)
    print("YUZU COMPANION - MCP DIAGNOSTIC")
    print("=" * 60)
    print()
    
    # Check token
    token = token or os.environ.get("ZO_ACCESS_TOKEN") or os.environ.get("ZO_MCP_TOKEN")
    if not token:
        print("[ERROR] No token found!")
        print("  Set ZO_ACCESS_TOKEN in your .env file")
        print("  Get token from: https://yuzu.zo.computer/?t=settings&s=advanced")
        print()
        return False
    
    print(f"[1] Token: {token[:20]}...{token[-10:]}")
    print()
    
    # Create client
    client = MCPClient(token=token)
    
    # Test connectivity
    print("[2] Testing MCP server connectivity...")
    try:
        available = await client.is_available()
        if available:
            print("    [OK] MCP server is reachable")
        else:
            print("    [WARN] MCP server health check failed")
    except Exception as e:
        print(f"    [ERROR] Connectivity failed: {e}")
        print()
        return False
    
    print()
    
    # Discover tools
    print("[3] Discovering available tools...")
    tools = await client.discover_tools()
    
    if not tools:
        print("    [WARN] No tools discovered")
    else:
        print(f"    [OK] Found {len(tools)} tools")
        print()
        print("    Available Tools:")
        print("    " + "-" * 50)
        for i, tool in enumerate(tools, 1):
            print(f"    {i:2d}. {tool.name}")
            if tool.description:
                desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
                print(f"        {desc}")
        print()
    
    # Test a simple tool execution
    print("[4] Testing tool execution...")
    print()
    
    # Try to list files (should work if token is valid)
    try:
        result = await client.execute("list_files", {"path": "/home"})
        if result.get("ok"):
            print("    [OK] Tool execution works!")
            print()
            print("    Sample output:")
            data = result.get("data", {})
            if isinstance(data, dict):
                for key in list(data.keys())[:5]:
                    print(f"      - {key}")
        else:
            print(f"    [WARN] Tool execution returned: {result.get('error', 'unknown')}")
    except Exception as e:
        print(f"    [ERROR] Tool execution failed: {e}")
    
    print()
    print("=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)
    
    return True


def main() -> None:
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Diagnostic for Yuzu Companion")
    parser.add_argument("--token", help="Zo MCP access token")
    args = parser.parse_args()
    
    try:
        import asyncio
        asyncio.run(run_diagnostic(args.token))
    except KeyboardInterrupt:
        print("\n[ABORTED] Diagnostic cancelled by user")


if __name__ == "__main__":
    main()