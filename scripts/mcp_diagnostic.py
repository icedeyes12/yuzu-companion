#!/usr/bin/env python3
"""
MCP Diagnostic Script for Yuzu Companion

Usage (from anywhere inside the project):
    cd /storage/emulated/0/projects/yuzu-companion
    python scripts/mcp_diagnostic.py

Or with inline token:
    ZO_ACCESS_TOKEN=your_token python scripts/mcp_diagnostic.py
"""

from __future__ import annotations

import asyncio
import os
import sys

# Dynamically add project root to path so imports work from anywhere
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)  # goes from scripts/ -> project root
sys.path.insert(0, _PROJECT_ROOT)


def main():
    token = os.environ.get("ZO_ACCESS_TOKEN", "")
    
    if not token:
        print("ERROR: ZO_ACCESS_TOKEN not set")
        print()
        print("Get your token from: https://yuzu.zo.computer/?t=settings&s=advanced")
        print("Add it to your .env file as ZO_ACCESS_TOKEN=...")
        print()
        print("Or run with inline token:")
        print("    ZO_ACCESS_TOKEN=your_token python scripts/mcp_diagnostic.py")
        return
    
    print(f"Token: {token[:20]}...")
    print()
    
    asyncio.run(_diagnose(token))


async def _diagnose(token: str):
    from app.mcp.client import MCPClient
    from app.dispatch.hybrid import HybridDispatcher
    
    print("[1] Testing MCP discovery...")
    client = MCPClient(token=token)
    tools = await client.discover_tools(force_refresh=True)
    print(f"   Discovered {len(tools)} MCP tools")
    if tools:
        print(f"   First tool: {tools[0].name}")
    print()
    
    print("[2] Testing MCP tool execution (web_search)...")
    result = await client.call_tool("web_search", {"query": "MCP protocol", "time_range": "anytime"})
    print(f"   ok: {result.get('ok')}")
    print(f"   markdown length: {len(result.get('markdown', ''))}")
    print()
    
    print("[3] Testing HybridDispatcher...")
    dispatcher = HybridDispatcher(mcp_token=token)
    await dispatcher.initialize()
    print(f"   Local tools: {len(dispatcher._local_tools)}")
    print(f"   MCP tools: {len(dispatcher._mcp_tools)}")
    print()
    
    print("[4] Testing unified dispatch (local)...")
    result = await dispatcher.execute("memory_search", {"query": "test"})
    print(f"   local memory_search: ok={result.get('ok')}")
    print()
    
    print("All tests passed!")
    print()
    print(f"Total tools available to Yuzuki: {len(dispatcher.get_all_tools())}")


if __name__ == "__main__":
    main()