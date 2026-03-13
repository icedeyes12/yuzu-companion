#!/bin/bash
# Yuzu Companion - Termux Setup Script
# Run this in Termux to set up Yuzu Companion on Android

set -e

YELLOW='\033[1;33m'
GREEN='\033[1;32m'
BLUE='\033[1;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                🍊 Yuzu Companion Setup                    ║"
echo "║                   For Termux/Android                      ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running in Termux
if [ -z "$TERMUX_VERSION" ] && [ -z "$TERMUX_API_VERSION" ]; then
    echo -e "${YELLOW}⚠️  Warning: Not running in Termux environment${NC}"
    echo "This script is designed for Termux on Android"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${BLUE}📦 Step 1: Updating packages...${NC}"
pkg update -y

echo -e "${BLUE}📦 Step 2: Installing dependencies...${NC}"
pkg install -y python python-pip git sqlite

# Install optional dependencies if available
echo -e "${BLUE}📦 Step 3: Installing optional tools...${NC}"
pkg install -y libffi openssl || true

# Set up storage access
if [ ! -d "$HOME/storage" ]; then
    echo -e "${BLUE}📂 Step 4: Setting up storage access...${NC}"
    termux-setup-storage || true
fi

# Create Yuzu directory
YUZU_DIR="$HOME/yuzu-companion"
if [ ! -d "$YUZU_DIR" ]; then
    echo -e "${BLUE}📂 Step 5: Creating Yuzu directory...${NC}"
    mkdir -p "$YUZU_DIR"
fi

cd "$YUZU_DIR"

# Check if already installed
if [ -f "$YUZU_DIR/web.py" ]; then
    echo -e "${YELLOW}⚠️  Yuzu Companion already installed${NC}"
    read -p "Reinstall/Update? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}📥 Backing up database...${NC}"
        if [ -f "$YUZU_DIR/yuzu_core.db" ]; then
            cp "$YUZU_DIR/yuzu_core.db" "$YUZU_DIR/yuzu_core.db.backup.$(date +%Y%m%d_%H%M%S)"
        fi
    else
        echo -e "${GREEN}✅ Skipping installation${NC}"
        exit 0
    fi
else
    echo -e "${BLUE}📥 Step 6: Downloading Yuzu Companion...${NC}"
    # Clone or download the project
    # For now, assume files are copied manually or via git
    echo -e "${YELLOW}⚠️  Please copy the yuzu-companion files to $YUZU_DIR${NC}"
    echo "You can use:"
    echo "  - termux-open to share files from phone"
    echo "  - git clone if you have the repo"
    echo "  - Or manually copy with a file manager"
    
    read -p "Press Enter when files are copied..."
fi

# Install Python dependencies
echo -e "${BLUE}🐍 Step 7: Installing Python packages...${NC}"
cd "$YUZU_DIR"
pip install --upgrade pip
pip install -r requirements.txt

# Create launcher script
echo -e "${BLUE}🚀 Step 8: Creating launcher...${NC}"

LAUNCHER_SCRIPT='$PREFIX/bin/yuzu'

sudo tee "$LAUNCHER_SCRIPT" > /dev/null << 'EOF'
#!/bin/bash
# Yuzu Companion Launcher for Termux

YUZU_DIR="$HOME/yuzu-companion"
cd "$YUZU_DIR"

# Termux-specific settings
export TERMUX_MODE=1
export TERMUX_HOME="$HOME"

# Server settings
export PORT=${PORT:-8080}
export HOST=${HOST:-0.0.0.0}

# Disable features that don't work in Termux
export NO_TIMG=1
export NO_TERMINAL_IMAGE_PREVIEW=1

echo "🍊 Starting Yuzu Companion..."
echo "📱 Access at:"
echo "   http://localhost:$PORT"
echo "   http://$(ifconfig 2>/dev/null | grep -oP 'inet \K[0-9.]+' | head -1):$PORT"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python web.py --host "$HOST" --port "$PORT"
EOF

chmod +x "$LAUNCHER_SCRIPT"

# Create Termux widget script
if [ -d "$HOME/.shortcuts" ] || mkdir -p "$HOME/.shortcuts" 2>/dev/null; then
    echo -e "${BLUE}📱 Step 9: Creating Termux Widget shortcut...${NC}"
    
    cat > "$HOME/.shortcuts/yuzu-quick" << 'EOF'
#!/bin/bash
cd $HOME/yuzu-companion
export TERMUX_MODE=1
export PORT=8080
export HOST=0.0.0.0
python web.py > /dev/null 2>&1 &
echo "Yuzu started on port 8080"
sleep 2
termux-open-url http://localhost:8080
EOF
    chmod +x "$HOME/.shortcuts/yuzu-quick"
fi

# Create desktop entry for Termux:X11 if available
if [ -d "$HOME/.termux" ]; then
    echo -e "${BLUE}🖥️  Step 10: Creating Termux:X11 desktop entry...${NC}"
    mkdir -p "$HOME/.local/share/applications"
    
    cat > "$HOME/.local/share/applications/yuzu.desktop" << 'EOF'
[Desktop Entry]
Name=Yuzu Companion
Comment=AI Companion for Termux
Exec=termux-open-url http://localhost:8080
Icon=utilities-terminal
Type=Application
Terminal=false
Categories=Network;Chat;
EOF
fi

# Create auto-start script (optional)
echo -e "${BLUE}⚙️  Step 11: Optional auto-start setup...${NC}"
read -p "Add Yuzu to Termux boot? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    mkdir -p "$HOME/.termux/boot"
    cat > "$HOME/.termux/boot/start-yuzu" << 'EOF'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
cd $HOME/yuzu-companion
export TERMUX_MODE=1
export PORT=8080
export HOST=0.0.0.0
nohup python web.py > $HOME/yuzu.log 2>&1 &
EOF
    chmod +x "$HOME/.termux/boot/start-yuzu"
    echo -e "${GREEN}✅ Auto-start enabled${NC}"
fi

# Final instructions
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  ✅ Setup Complete!                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Usage:${NC}"
echo "  yuzu              - Start Yuzu Companion"
echo "  yuzu-quick        - Quick start with auto-open (if widget installed)"
echo ""
echo -e "${BLUE}Access URLs:${NC}"
echo "  http://localhost:8080"
echo "  http://$(ifconfig 2>/dev/null | grep -oP 'inet \K[0-9.]+' | head -1):8080"
echo ""
echo -e "${YELLOW}⚠️  Important Notes:${NC}"
echo "  - Keep Termux running in background for continuous access"
echo "  - Use 'termux-wake-lock' to prevent Android from killing the process"
echo "  - Images are stored in ~/storage/ for easy access"
echo ""
echo -e "${GREEN}🍊 Enjoy your time with Yuzu!${NC}"
