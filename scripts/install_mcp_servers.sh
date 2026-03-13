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

# Install uvx if not present (required for some MCP servers)
if ! command -v uvx &> /dev/null; then
    echo "📦 Installing uvx..."
    if command -v pip &> /dev/null; then
        pip install uvx || pip install --user uvx
    else
        echo "❌ pip not found. Please install pip first."
        exit 1
    fi
fi

# Core MCP servers (via npx - no local install needed)
echo ""
echo "📦 Core servers (via npx - no install needed):"
echo "  - @modelcontextprotocol/server-filesystem"
echo "  - @modelcontextprotocol/server-sqlite"  
echo "  - @modelcontextprotocol/server-memory"
echo "  These will be fetched on first use."

# Install via uvx (Python-based MCP servers)
echo ""
echo "📦 Installing via uvx:"
echo "  - mcp-server-fetch"
uvx install mcp-server-fetch || echo "  ⚠️ Failed (may need: pip install mcp-server-fetch)"

echo ""
echo "📦 Optional servers (install if needed):"
echo "  # Git support:"
echo "  uvx install mcp-server-git"
echo ""
echo "  # Time utilities:"
echo "  uvx install mcp-server-time"
echo ""
echo "  # Puppeteer browser:"
echo "  npm install -g @modelcontextprotocol/server-puppeteer"
echo ""

echo "======================================"
echo "✅ MCP packages installed!"
echo ""
echo "Next step: Run the setup script"
echo "  python scripts/setup_mcp_servers.py"
echo ""
echo "Then restart Yuzu Companion to apply changes"
