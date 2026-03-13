#!/bin/bash
# ============================================
# Install MCP Servers for Yuzu Companion
# ============================================
# This script installs MCP server packages
# Run: bash scripts/install_mcp_servers.sh
# ============================================

set -e

echo "🍊 Installing MCP server packages..."
echo "======================================"

# Check if pip is available
if ! command -v pip &> /dev/null; then
    echo "❌ pip not found. Please install python-pip first:"
    echo "   pkg install python-pip"
    exit 1
fi

# Python-based MCP servers (via pip)
echo ""
echo "📦 Installing Python MCP servers:"

# mcp-server-fetch
if pip show mcp-server-fetch &> /dev/null; then
    echo "  ✅ mcp-server-fetch already installed"
else
    echo "  📥 Installing mcp-server-fetch..."
    pip install mcp-server-fetch && echo "  ✅ Done" || echo "  ⚠️ Failed"
fi

echo ""
echo "📦 Core servers (via npx - no install needed):"
echo "  - @modelcontextprotocol/server-filesystem"
echo "  - @modelcontextprotocol/server-sqlite"
echo "  - @modelcontextprotocol/server-memory"
echo "  - @modelcontextprotocol/server-github"
echo "  These will be fetched automatically on first use."

echo ""
echo "📦 Optional servers (uncomment in setup_mcp_servers.py to enable):"
echo "  - mcp-server-git (pip install mcp-server-git)"
echo "  - mcp-server-time (pip install mcp-server-time)"

echo ""
echo "======================================"
echo "✅ MCP installation complete!"
echo ""
echo "Next step: Configure servers in database"
echo "  python scripts/setup_mcp_servers.py"
echo ""
echo "Then restart Yuzu Companion"
