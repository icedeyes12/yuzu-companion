# Installation Guide

Complete setup instructions for Yuzu Companion.

## Table of Contents

1. [Requirements](#requirements)
2. [Standard Installation](#standard-installation)
3. [Termux (Android) Installation](#termux-android-installation)
4. [Configuration](#configuration)
5. [Troubleshooting](#troubleshooting)

---

## Requirements

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.9 | 3.11+ |
| RAM | 512 MB | 1 GB |
| Storage | 100 MB | 500 MB |
| Network | Optional | Required for AI providers |

### Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Linux | Fully supported | Primary development platform |
| macOS | Supported | Intel and Apple Silicon |
| Windows (WSL) | Supported | Use WSL2 for best experience |
| Termux (Android) | Supported | See Termux section below |

---

## Standard Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/icedeyes12/yuzu-companion.git
cd yuzu-companion
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Initialise Database

```bash
python -c "from database import init_db; init_db()"
```

### Step 5: Start Application

**Web Interface:**
```bash
python web.py
```

**Terminal Interface:**
```bash
python main.py
```

Access web interface at `http://localhost:5000`

---

## Termux (Android) Installation

### Prerequisites

Install Termux from F-Droid (NOT Play Store):
- https://f-droid.org/packages/com.termux/

### Automated Setup

```bash
curl -fsSL https://raw.githubusercontent.com/icedeyes12/yuzu-companion/main/termux-setup.sh | bash
```

Or manually:

```bash
# Update packages
pkg update && pkg upgrade -y

# Install dependencies
pkg install python git -y

# Clone repository
git clone https://github.com/icedeyes12/yuzu-companion.git
cd yuzu-companion

# Install Python dependencies
pip install -r requirements.txt

# Start with mobile-optimised settings
python web.py --host 0.0.0.0 --port 8080
```

### Post-Install (Termux)

1. Note the IP address displayed on startup
2. Open browser on your device
3. Navigate to `http://localhost:8080` or the displayed IP
4. Add to Home Screen for PWA support

---

## Configuration

### API Keys (Required)

Configure at least one AI provider:

| Provider | Key Source | Free Tier |
|----------|------------|-----------|
| OpenRouter | https://openrouter.ai/keys | Yes |
| Cerebras | https://cerebras.ai/ | Yes |
| Chutes | https://chutes.ai/ | Yes |
| Ollama | Local | N/A |

Add keys via web interface: **Config > API Keys**

### Profile Settings

Set in web interface: **Config > Profile Settings**

| Setting | Description | Default |
|---------|-------------|---------|
| Display Name | Your name in chats | User |
| Partner Name | AI companion name | Yuzu |
| Affection Level | Relationship warmth | 85 |

### Provider Selection

Navigate to **Config > AI Provider Settings**

1. Select preferred provider from dropdown
2. Choose model from available options
3. Click "Test Connection" to verify
4. Click "Save Provider Settings"

### Vision Model (Optional)

For image analysis, select a vision-capable model:

**Config > Vision Model**

| Model | Provider | Best For |
|-------|----------|----------|
| moonshotai/Kimi-K2.5-TEE | Chutes | General vision |
| Qwen/Qwen3.5-397B-A17B-TEE | Chutes | High-res images |

### Image Generation (Optional)

**Config > Image Generation Model**

| Model | Speed | Quality |
|-------|-------|---------|
| Hunyuan | Fast | Good |
| Z Image Turbo | Very Fast | Acceptable |

---

## Troubleshooting

### Database Issues

| Symptom | Solution |
|---------|----------|
| Database locked | Stop other instances, delete `*.db-journal` |
| Corruption error | Restore from backup or delete `yuzu_core.db` |
| Migration failed | Run `python -c "from database import init_db; init_db()"` |

### Provider Connection Failed

| Issue | Check |
|-------|-------|
| API key invalid | Verify key at provider dashboard |
| Rate limited | Wait or switch provider |
| Timeout | Check internet connection |
| Model unavailable | Select different model |

### Web Interface Not Loading

```bash
# Check if port is in use
lsof -i :5000

# Use different port
python web.py --port 8080

# Bind to all interfaces (for mobile access)
python web.py --host 0.0.0.0
```

### Termux Specific Issues

| Issue | Solution |
|-------|----------|
| Permission denied | Run `termux-setup-storage` |
| pip install fails | Use `pip install --no-cache-dir` |
| Out of memory | Close other apps, add swap |
| Cannot access from other devices | Use `--host 0.0.0.0` |

### Getting Help

1. Check [docs/README.md](README.md) for architecture details
2. Review [logs](#logs) for error messages
3. Open issue: https://github.com/icedeyes12/yuzu-companion/issues

### Logs

Log locations:
- Terminal output: Console
- Web errors: Browser DevTools (F12) > Console
- Database: `yuzu_core.db` (SQLite)

Enable debug mode:
```bash
python web.py --debug
```

### MCP Server Configuration

MCP (Model Context Protocol) servers extend Yuzu Companion with additional tools and capabilities. This is optional and not required for basic usage.

#### Prerequisites

- Node.js 18+ (for running MCP servers)
- npm or npx

#### Installation

1. Install required MCP servers:
```bash
# Filesystem server (read/write local files)
npm install -g @modelcontextprotocol/server-filesystem

# Fetch server (fetch any URL)
npm install -g mcp-server-fetch

# SQLite server (query SQLite databases)
npm install -g @modelcontextprotocol/server-sqlite
```

2. Configure MCP servers via web interface: **Config > MCP Servers**

3. Add server configuration:
```json
{
  "name": "filesystem",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/notes"],
  "env": {},
  "auto_start": true
}
```

#### Available MCP Servers

| Server | Use Case | Install |
|--------|----------|---------|
| `@modelcontextprotocol/server-filesystem` | Read/write local files | `npx -y @modelcontextprotocol/server-filesystem <path>` |
| `mcp-server-fetch` | Fetch any URL | `npx -y mcp-server-fetch` |
| `@modelcontextprotocol/server-sqlite` | Query SQLite databases | `npx -y @modelcontextprotocol/server-sqlite <db-path>` |
| `@modelcontextprotocol/server-memory` | Persistent key-value storage | `npx -y @modelcontextprotocol/server-memory` |

#### Termux (Android)

For Termux, use npx with the `-y` flag:
```json
{
  "name": "notes",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/sdcard/Documents/yuzu-notes"]
}
```

#### Security

- Only enable servers you need
- Review server permissions before enabling
- Keep servers updated

#### Troubleshooting

- Server fails to start: Check Node.js version (`node --version`)
- Connection refused: Ensure server is running and port is correct
- Permission denied: Check file/directory permissions

---

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `FLASK_ENV` | Development mode | `development` |
| `FLASK_PORT` | Server port | `8080` |
| `YUZU_DATA_DIR` | Custom data path | `/path/to/data` |

---

## Next Steps

After installation:

1. Configure API keys
2. Set your profile
3. Start a chat session
4. Explore Config page for advanced settings

See [README.md](README.md) for full architecture documentation.

---

## 🆕 Clean Architecture Setup (Advanced)

For developers working with the new Clean Architecture structure.

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| pytest | 7.0+ |
| SQLite | 3.35+ |

### New Architecture Installation

```bash
# Install with dev dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio  # For testing

# Verify imports work
python -c "import sys; sys.path.insert(0, 'src'); from yuzu.domain.models import Profile; print('✅ Clean Architecture imports OK')"
```

### Running Tests

```bash
# All tests
cd yuzu-companion
python -m pytest tests/unit/ tests/integration/ -v

# With coverage
python -m pytest --cov=src/yuzu tests/

# Specific test file
python -m pytest tests/unit/test_chat_handler.py -v
```

### Feature Flag Configuration

Create `.env` file for local development:

```bash
# .env
YUZU_USE_NEW_DB=false
YUZU_USE_NEW_CHAT=false
YUZU_USE_NEW_PROVIDERS=false
YUZU_USE_NEW_TOOLS=false
YUZU_DEBUG=true
```

Or set inline:
```bash
YUZU_USE_NEW_CHAT=true python web.py
```

### Shadow Mode Testing

Enable side-by-side comparison:

```bash
# Shadow mode compares old vs new implementations
YUZU_SHADOW_MODE=true YUZU_SHADOW_LOG_LEVEL=debug python web.py
```

Logs written to: `logs/shadow_mode/YYYY-MM-DD.jsonl`

### Provider Testing (New Architecture)

```bash
# Test new Ollama provider with circuit breaker
python -c "
import sys
sys.path.insert(0, 'src')
from yuzu.infrastructure.ai.providers.ollama import OllamaProvider
from yuzu.infrastructure.config.container import get_container

provider = OllamaProvider()
print(f'Available: {provider.is_available}')
print(f'Models: {provider.get_models()[:3]}...')
"
```

### Architecture Verification

```bash
# Verify no circular dependencies
python -c "
import sys
sys.path.insert(0, 'src')
from yuzu.domain.models import Profile
from yuzu.domain.services import ChatService
from yuzu.infrastructure.ai import get_provider_registry
from yuzu.application.handlers import get_chat_handler
from yuzu.interfaces.cli import get_cli_adapter
print('✅ All layers import successfully')
"
```

### Migration Checklist

For contributors working on the migration:

- [ ] Tests pass: `python -m pytest tests/ -q`
- [ ] No circular imports: Verify with script above
- [ ] Feature flags work: Toggle via env vars
- [ ] Shadow mode clean: No major discrepancies
- [ ] Documentation updated: This README section

### Debugging New Architecture

```bash
# Enable debug logging
YUZU_DEBUG=true python main.py

# Run specific component in isolation
python -m pytest tests/unit/test_chat_handler.py::TestChatHandler::test_handle_message -v -s

# Profile performance
python -m cProfile -o profile.stats -c "
import sys
sys.path.insert(0, 'src')
from yuzu.application.handlers.chat_handler import handle_user_message
handle_user_message('Hello', 'test')
"
```

### Clean Architecture Development Workflow

1. **Make changes** in `src/yuzu/`
2. **Run tests**: `python -m pytest tests/`
3. **Check shadow mode**: Enable and compare
4. **Update docs**: Add ADR to `.agent/archive/`
5. **Commit**: With clear migration phase tag

### Troubleshooting New Architecture

| Issue | Cause | Solution |
|-------|-------|----------|
| ImportError: No module named 'yuzu' | Path not set | `sys.path.insert(0, 'src')` |
| Feature flag not working | Env var name | Check `YUZU_` prefix |
| Shadow mode not logging | Log dir missing | `mkdir -p logs/shadow_mode` |
| Test failures after changes | Breaking change | Update tests or use adapter pattern |

