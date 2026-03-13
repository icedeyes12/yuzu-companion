# Yuzu Companion - Installation Guide

## Quick Start

### Option 1: Termux (Android) - Easiest

```bash
# 1. Install Termux from F-Droid (NOT Play Store)
# https://f-droid.org/packages/com.termux/

# 2. Run the setup script
curl -fsSL https://raw.githubusercontent.com/icedeyes12/yuzu-companion/main/termux-setup.sh | bash

# 3. Start Yuzu
/yuzu
```

Then open your browser to `http://localhost:8080`

### Option 2: Standard Python Install

```bash
# 1. Clone the repository
git clone https://github.com/icedeyes12/yuzu-companion.git
cd yuzu-companion

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
python web.py
```

Then open your browser to `http://localhost:5000`

---

## Detailed Installation

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- 500MB free disk space
- Internet connection (for AI providers)

### Step-by-Step Installation

#### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- Flask 3.0+ (web framework)
- SQLAlchemy 2.0+ (database)
- pycryptodome 3.20+ (encryption)
- requests 2.31+ (HTTP client)
- rich 13.0+ (terminal UI)
- beautifulsoup4 4.12+ (HTML parsing)

#### 2. Configure AI Providers

Yuzu Companion supports multiple AI providers:

**Ollama (Local - Recommended for privacy)**
```bash
# Install Ollama from https://ollama.com
# Then pull a model:
ollama pull llama3.1:8b
```

**OpenRouter (Cloud - More models)**
1. Get API key from https://openrouter.ai/keys
2. Add key in Config page or via API:
```bash
curl -X POST http://localhost:5000/api/add_api_key \
  -H "Content-Type: application/json" \
  -d '{"key_name": "openrouter", "api_key": "sk-or-v1-..."}'
```

**Chutes (Cloud)**
1. Get API key from https://chutes.ai/
2. Add via Config page

**Cerebras (Cloud)**
1. Get API key from https://cerebras.ai/
2. Add via Config page

#### 3. Start the Server

```bash
# Default (localhost:5000)
python web.py

# Custom port
python web.py --port 8080

# Allow external connections (for mobile access)
python web.py --host 0.0.0.0 --port 8080

# Debug mode
python web.py --debug
```

#### 4. Access the Interface

Open your web browser:
- Local: http://localhost:5000
- Network: http://your-ip:5000

---

## Termux-Specific Setup

### Why Termux?

Termux allows running Yuzu Companion directly on Android devices without root access. Perfect for:
- Private AI conversations on your phone
- No cloud dependencies (with local Ollama)
- Full control over your data

### Installation Steps

1. **Install Termux**
   - Download from F-Droid: https://f-droid.org/packages/com.termux/
   - ⚠️ Do NOT use the Play Store version (outdated)

2. **Run Setup Script**
   ```bash
   termux-setup-storage
   curl -fsSL https://raw.githubusercontent.com/icedeyes12/yuzu-companion/main/termux-setup.sh | bash
   ```

3. **Start Yuzu**
   ```bash
   yuzu
   ```

4. **Access**
   - In Termux: http://localhost:8080
   - From phone browser: http://localhost:8080
   - From other devices: http://phone-ip:8080

### Termux Tips

**Keep Server Running**
```bash
# Prevent Android from killing Termux
termux-wake-lock

# Run in background
nohup yuzu > yuzu.log 2>&1 &
```

**Auto-start on Boot**
```bash
# Install Termux:Boot from F-Droid
# Create startup script
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-yuzu << 'EOF'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
cd ~/yuzu-companion
export TERMUX_MODE=1
nohup python web.py --host 0.0.0.0 --port 8080 > yuzu.log 2>&1 &
EOF
chmod +x ~/.termux/boot/start-yuzu
```

**Access Generated Images**
```bash
# Images are saved to:
~/yuzu-companion/static/generated_images/

# Or via storage:
~/storage/shared/yuzu-images/
```

---

## Troubleshooting

### Port Already in Use
```bash
# Find and kill process using port 5000
lsof -ti:5000 | xargs kill -9

# Or use different port
python web.py --port 8080
```

### Database Errors
```bash
# Reset database (WARNING: loses all chat history)
rm yuzu_core.db
python web.py  # Will recreate fresh database
```

### Module Not Found
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Termux: No Module Named 'flask'
```bash
# Ensure pip installs to correct location
pip install --user -r requirements.txt
# Or
python -m pip install -r requirements.txt
```

### Images Not Loading
1. Check `static/uploads/` directory exists
2. Verify write permissions: `chmod -R 755 static/`
3. For Termux: ensure storage permission granted

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server bind address | `127.0.0.1` |
| `PORT` | Server port | `5000` |
| `TERMUX_MODE` | Enable Termux optimizations | `0` |
| `DEBUG` | Enable Flask debug mode | `0` |

### Example .env file
```bash
HOST=0.0.0.0
PORT=8080
DEBUG=0
```

---

## Security Notes

- Default binding is `127.0.0.1` (localhost only)
- Use `0.0.0.0` only on trusted networks
- API keys are encrypted with ChaCha20-Poly1305
- Messages are NOT encrypted by default (stored as plaintext)

---

## Next Steps

1. Open Config page to set up AI providers
2. Customize your companion's name and personality
3. Start chatting!

For help, visit: https://github.com/icedeyes12/yuzu-companion/issues
