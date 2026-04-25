# Zo MCP Client

Bridges Yuzuki to Zo Computer's MCP sandbox — giving her access to 72+ tools including file operations, web search, browser automation, and more.

## Setup

### 1. Get Your Zo Access Token

1. Go to [Zo Settings → Advanced](https://yuzu.zo.computer/?t=settings&s=advanced)
2. Create an access token in the **Access Tokens** section
3. Copy the token value

### 2. Add to Your `.env`

```bash
# In your yuzu-companion/.env file:
ZO_ACCESS_TOKEN=zo_sk_your_token_here
```

### 3. Test the Connection

```bash
cd /storage/emulated/0/projects/yuzu-companion
python scripts/mcp_diagnostic.py
```

Expected output:
```
[1] Testing MCP discovery...
   Discovered 56 MCP tools
   First tool: web_search
```

## Available Tools

### File/Code Tools
| Tool | Description |
|------|-------------|
| `read_file` | Read any text file in the workspace |
| `edit_file` | Deterministic edits (replace, insert, delete blocks) |
| `edit_file_llm` | LLM-assisted edits with context awareness |
| `create_or_rewrite_file` | Create or fully rewrite files |
| `grep_search` | Search by filename or content |
| `list_files` | List directory contents in tree structure |
| `run_bash_command` | Execute shell commands |
| `run_sequential_cmds` | Run multiple commands in sequence |
| `run_parallel_cmds` | Run multiple commands concurrently |

### Web/Research Tools
| Tool | Description |
|------|-------------|
| `web_search` | Broad web search with time filters |
| `web_research` | Deep research with category filters |
| `read_webpage` | Extract content from web pages |
| `x_search` | Search X/Twitter posts |
| `maps_search` | Google Maps search |

### Browser Tools
| Tool | Description |
|------|-------------|
| `open_webpage` | Navigate to a URL |
| `view_webpage` | Get current page content + screenshot |
| `use_webpage` | Interact with page (click, fill, scroll) |

### Media Tools
| Tool | Description |
|------|-------------|
| `generate_image` | Generate images |
| `edit_image` | Edit existing images |
| `generate_video` | Generate short videos |
| `transcribe_audio` | Transcribe audio files |
| `transcribe_video` | Transcribe video files |

### Zo Space Tools
| Tool | Description |
|------|-------------|
| `list_space_routes` | List all routes |
| `get_space_route` | Get route source code |
| `write_space_route` | Create/rewrite routes |
| `edit_space_route` | Edit routes (partial edits) |
| `delete_space_route` | Delete routes |
| `update_space_settings` | Update space settings |
| `list_space_assets` | List uploaded assets |
| `update_space_asset` | Upload assets |

### Agent/Automation Tools
| Tool | Description |
|------|-------------|
| `create_agent` | Create scheduled agents |
| `list_agents` | List existing agents |
| `get_automation` | Get agent details |
| `edit_agent` | Update agent configuration |
| `delete_agent` | Delete agents |
| `create_automation` | Create automations |
| `list_automations` | List automations |
| `create_rule` | Create behavioral rules |
| `list_rules` | List rules |
| `tool_docs` | Get tool documentation |

### Integration Tools
| Tool | Description |
|------|-------------|
| `list_app_tools` | List connected app tools |
| `use_app_*` | Use any connected app (gmail, calendar, etc.) |

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Yuzuki Companion                     │
├──────────────────────────────────────────────────────┤
│  app/orchestrator_agentic.py                        │
│    │  Agentic Plan-Execute-Observe loop              │
│    │                                                │
│    ▼                                                │
│  app/dispatch/hybrid.py                             │
│    │  Unified tool dispatcher                        │
│    │  Priority: local tools → Zo MCP               │
│    │                                                │
│    ├──► app/tools/registry.py    (local tools)      │
│    │     └── memory_search, image_generate, etc.    │
│    │                                                │
│    └──► app/mcp/client.py        (Zo MCP)           │
│          └── 72+ Zo tools via JSON-RPC 2.0         │
└──────────────────────────────────────────────────────┘
                        │
                        ▼
            ┌─────────────────────────┐
            │  https://api.zo.computer/mcp │
            │      (Zo MCP Sandbox)     │
            └─────────────────────────┘
```

## How It Works

### JSON-RPC 2.0 Protocol

Zo MCP uses standard JSON-RPC 2.0:

```python
# Request
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "call_tool",
    "params": {
        "name": "web_search",
        "arguments": {"query": "test", "time_range": "anytime"}
    }
}

# Response
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "content": [{"type": "text", "text": "..."}]
    }
}
```

### Tool Discovery

On startup, Yuzuki discovers available tools:

```python
client = MCPClient(token=token)
tools = await client.discover_tools()
# Returns list of MCPTool objects with name, description, parameters
```

### Tool Execution

```python
result = await client.execute("web_search", {
    "query": "MCP protocol",
    "time_range": "anytime"
})
# Returns: {"ok": True, "content": [...], "is_error": False}
```

### Hybrid Dispatch

The `HybridDispatcher` routes tools intelligently:

```python
dispatcher = HybridDispatcher(mcp_token=token)
await dispatcher.initialize()

# Local tools take priority
result = await dispatcher.execute("memory_search", {"query": "..."})

# MCP tools for everything else
result = await dispatcher.execute("web_search", {"query": "..."})
```

## Troubleshooting

### "Authentication failed"

Your token is invalid or expired. Get a new one from [Zo Settings](https://yuzu.zo.computer/?t=settings&s=advanced).

### "Connection refused"

Check your internet connection. The MCP endpoint is at `https://api.zo.computer/mcp`.

### "Tool not found"

Some tools may not be available depending on your Zo plan. Run the diagnostic script to see which tools are available.

### Zero tools discovered

```bash
# Debug with verbose logging
python -c "
import asyncio
import logging
logging.basicConfig(level=logging.DEBUG)

from app.mcp.client import MCPClient
client = MCPClient(token='your_token')
tools = asyncio.run(client.discover_tools())
print(f'Found {len(tools)} tools')
"
```

## Files

```
app/mcp/
├── __init__.py      # Package exports
├── client.py         # MCP client implementation
└── README.md         # This file
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ZO_ACCESS_TOKEN` | Zo Computer access token | Yes |
