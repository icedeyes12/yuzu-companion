#!/bin/bash
# Install MCP servers locally for offline use
# Run this once to pre-download all MCP server packages

set -e

echo "🍊 Installing MCP servers for Yuzu Companion..."
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if node/npm is installed
if ! command -v npm &> /dev/null; then
    echo -e "${YELLOW}⚠️  npm not found. Installing Node.js...${NC}"
    if command -v apt-get &> /dev/null; then
        apt-get update
        apt-get install -y nodejs npm
    elif command -v pkg &> /dev/null; then
        pkg install -y nodejs
    else
        echo "❌ Cannot install Node.js automatically"
        echo "Please install Node.js manually: https://nodejs.org"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Node.js found:${NC} $(node --version)"
echo ""

# Create local npm directory for MCP servers
MCP_DIR="$HOME/.mcp-servers"
mkdir -p "$MCP_DIR"
cd "$MCP_DIR"

# Initialize package.json if not exists
if [ ! -f "package.json" ]; then
    echo "📦 Creating package.json..."
    cat > package.json << 'EOF'
{
  "name": "yuzu-mcp-servers",
  "version": "1.0.0",
  "description": "MCP servers for Yuzu Companion",
  "private": true
}
EOF
fi

echo "📥 Installing MCP server packages..."
echo ""

# Install filesystem server
echo "  📁 @modelcontextprotocol/server-filesystem..."
npm install @modelcontextprotocol/server-filesystem --save --silent 2>&1 | grep -v "npm WARN" || true
echo -e "  ${GREEN}✓${NC} filesystem"

# Install fetch server (using uvx alternative - mcp-server-fetch)
echo "  🌐 mcp-server-fetch..."
npm install mcp-server-fetch --save --silent 2>&1 | grep -v "npm WARN" || true
echo -e "  ${GREEN}✓${NC} fetch"

# Install sqlite server
echo "  🗄️  @modelcontextprotocol/server-sqlite..."
npm install @modelcontextprotocol/server-sqlite --save --silent 2>&1 | grep -v "npm WARN" || true
echo -e "  ${GREEN}✓${NC} sqlite"

# Install memory server
echo "  🧠 @modelcontextprotocol/server-memory..."
npm install @modelcontextprotocol/server-memory --save --silent 2>&1 | grep -v "npm WARN" || true
echo -e "  ${GREEN}✓${NC} memory"

echo ""
echo -e "${GREEN}✅ All MCP servers installed!${NC}"
echo ""
echo "📂 Location: $MCP_DIR"
echo ""
echo "Next steps:"
echo "  1. Restart Yuzu Companion: python web.py"
echo "  2. Check MCP status in Config page"
echo ""
echo "Installed packages:"
ls -la node_modules/.bin/ 2>/dev/null | grep -E "(filesystem|fetch|sqlite|memory)" || echo "  (check $MCP_DIR/node_modules/.bin/)"
