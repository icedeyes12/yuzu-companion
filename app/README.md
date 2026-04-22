# Yuzu Companion — Application Module

The `app/` directory is the core of Yuzu Companion — the AI companion system that powers emotional, long-running conversations with persistent memory across sessions.


---

## Table of Contents

- [Overview](#overview)
- [Directory Structure](#directory-structure)
- [Core Entry Points](#core-entry-points)
  - [`file app.py`](#apppy--orchestration-core)
  - [`file main.py`](#mainpy--cli-application)
  - [`file web.py`](#webpy--fastapi-web-server)
- Database Layer
- [AI Provider System](#ai-provider-system)
- [Tool System](#tool-system)
- [Memory System](#memory-system)
- [Multimodal System](#multimodal-system)
- [Encryption](#encryption)
- [Session Management](#session-management)
- [Configuration](#configuration)
- [Workflow: Message Processing](#workflow-message-processing)
- [Dependencies](#dependencies)
- [Architecture Principles](#architecture-principles)

---


## Overview

Yuzu Companion is a multi-interface AI companion with:

- **Emotional bonding** — affection system, personality memory, relationship continuity
- **Multimodal interaction** — text, images, vision analysis, image generation
- **Session-based memory** — episodic + semantic long-term memory with FSRS-inspired retention
- **Encrypted conversations** — ChaCha20-Poly1305 encryption for API keys
- **Three interfaces** — Terminal (Rich UI), Web (FastAPI), and programmatic (CLI/API)

```
graph LR
    A[User] --> B[main.py - CLI Entry]
    A --> C[web.py - Web Server]
    A --> D[External - API Calls]

    B --> E[app.py - Core Logic]
    C --> E
    D --> E

    E --> F[(Database - PostgreSQL)]
    E --> G[AI Providers - Ollama/Cerebras/OpenRouter/Chutes]
    E --> H[Tools - ImageGen/Search/Memory]
    E --> I[Memory System - episodic + semantic]
```

---

## Directory Structure

```
app/
├── app.py                 # Thin entry point → orchestrator
├── orchestrator.py        # Message handling pipeline
├── llm_client.py          # AI response generation
├── commands.py            # /command detection + StreamFilter
├── prompts.py             # System prompt assembly
├── profile_analysis.py    # Profile + memory analysis
├── session_lifecycle.py   # Session start/end
├── logging_config.py      # Centralized logging
├── visual_context.py      # Visual context buffer
├── providers.py           # AI provider abstraction
├── db_pg.py               # PostgreSQL connection pool
├── db_queries.py          # SQL constants + parsers
├── db_pg_models.py        # Sync CRUD wrappers
├── db_pg_models_async.py  # Async CRUD wrappers
├── encryption.py          # ChaCha20-Poly1305 for API keys
├── key_manager.py         # Key derivation
├── api/                   # API routing package
│   ├── __init__.py        # Exposes api_router
│   └── routes.py          # All /api/* endpoints
├── memory/                # Memory subsystem
│   ├── db_memory.py       # Unified memory CRUD
│   ├── db_memory_queries.py # SQL constants
│   ├── retrieval.py       # Hybrid retrieval (RRF + FSRS)
│   ├── extractor.py       # Fact extraction
│   ├── memory.py          # Background pipeline
│   ├── memory_review.py   # LLM-based review
│   ├── pcl.py             # Predict-Calibrate Learning
│   ├── review.py          # FSRS decay
│   └── embedder.py        # Chutes embedding API
└── tools/                 # Tool system
    ├── registry.py        # Central dispatch
    ├── schemas.py         # ToolDefinition + ToolParam
    ├── multimodal.py      # Vision routing
    ├── image_generate.py  # Image generation
    ├── http_request.py    # HTTP requests
    ├── memory_store.py    # Store facts
    └── memory_search.py   # Search memories
```

**Removed/Deprecated:**

- `file database.py` — deleted (use `file db_pg_models.py` directly)
- `file memory/models.py` — deleted (no ORM layer)
- `file memory/segmenter.py` — merged into `file memory.py`
- `file memory/vector_store.py` — deprecated stub

---

## Core Entry Points

### `file orchestrator.py` — Message Orchestration

The single entry point for handling user messages. Coordinates:

1. Image caching from user messages
2. Vision model routing when images detected
3. **Standard tool calling** — `tool_calls` from LLM + legacy `/command` fallback
4. Memory pipeline triggering
5. Response generation via provider selection

### `file app.py` — Core Application Facade

Simplified facade that delegates to `file orchestrator.py` for backward compatibility.\
Key functions:

- `handle_user_message()` — synchronous response
- `handle_user_message_streaming()` — streaming response
- `start_session()` — initialize session, run memory pipeline
- `summarize_memory()` — per-session context update
- `summarize_global_player_profile()` — cross-session profile analysis

### `file main.py` — CLI Application

Terminal interface using Rich + prompt_toolkit. Provides:

- Interactive chat loop with command handling (`/model`, `/imagine`, `/vision`, `/session`, etc.)
- Session management menu
- Provider/model switching
- Code block extraction and saving
- Web interface launcher

### `file web.py` — FastAPI Entry Point

Minimal entry point that sets up the web server:

- Static mounts (`/static`, `/uploads`, `/generated_images`)
- HTML page routes (`/`, `/chat`, `/config`, `/about`)
- Registers `api_router` from `file app/api/routes.py`

All API endpoints are defined in `file app/api/routes.py`.

---

## API Routing

### `file api/__init__.py`

Package init that exposes `api_router` for registration in `file web.py`.

### `file api/routes.py`

All `/api/*` endpoints (\~700 lines):

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/config` | GET | Frontend SSOT for vision models |
| `/api/send_message` | POST | Synchronous message handling |
| `/api/send_message_stream` | POST | Streaming message handling |
| `/api/get_profile` | GET | Profile data |
| `/api/providers/*` | \* | Provider management |
| `/api/sessions/*` | \* | Session CRUD |
| `/api/memory_stats` | GET | Memory statistics |

**Key endpoint:** `/api/config`

Returns dynamic configuration for the frontend:

```json
{
  "status": "success",
  "vision": {
    "models_by_provider": {
      "chutes": ["Qwen/Qwen3.5-397B-A17B-TEE", ...],
      "openrouter": ["moonshotai/kimi-k2.5"]
    },
    "current_provider": "chutes",
    "current_model": "Qwen/Qwen3.5-397B-A17B-TEE"
  }
}
```

This eliminates hardcoded vision model lists in `file static/js/config.js`.

---

## Database Layer

### `file db_pg.py` — Connection Pool

PostgreSQL connection management using `ThreadedConnectionPool` with context managers:

- `PgSession` — sync context manager for database operations
- `AsyncPgSession` — async context manager for FastAPI routes
- `pg_fetchone`, `pg_fetchall`, `pg_execute` — convenience functions

### `file db_pg_models.py` — CRUD Operations

Direct PostgreSQL CRUD operations using raw psycopg2. All data in PostgreSQL (`yuzuki`).

```
erDiagram
    PROFILE ||--o{ CHAT_SESSION : has
    CHAT_SESSION ||--o{ MESSAGE : contains

    PROFILE {
        int id PK
        string display_name
        string partner_name
        int affection
        string memory_json
        json providers_config_json
        json context
        string image_model
        string vision_model
    }

    CHAT_SESSION {
        int id PK
        string name
        bool is_active
        int message_count
        json memory_json
    }

    MESSAGE {
        int id PK
        int session_id FK
        string role
        string content
        bool content_encrypted
        string timestamp
    }

    SEMANTIC_FACTS {
        int id PK
        int session_id FK
        string fact_type
        text content
        vector embedding
        jsonb metadata
        timestamp created_at
        timestamp last_accessed
    }
```

**Key tables:**

- `profiles` — user/companion settings, memory JSON, provider config
- `chat_sessions` — session tracking, per-session memory
- `messages` — conversation log (role, content, timestamp, image_paths)
- `api_keys` — encrypted API key storage
- `semantic_facts` — unified memory table with pgvector embeddings
  - `fact_type='static'` — semantic memories (stable facts)
  - `fact_type='dynamic'` — episodic memories and segments (decayable)

### `file db_queries.py` — SQL Constants

Single source of truth for SQL strings, schema DDL, and row parsers. Used by both sync and async repository layers.

**Safety rules:**

- NEVER drops tables
- Only safe migrations (add columns, never destructive)
- Aborts if database corruption detected

---

## AI Provider System

### `file providers.py`

Pluggable provider architecture:

```
classDiagram
    class AIProvider {
        +name: str
        +config: Dict
        +is_available: bool
        +get_models()
        +send_message()
        +send_message_streaming()
        +supports_vision()
        +format_vision_message()
    }

    class OllamaProvider {
        +base_url: str
        +available_models: List
    }

    class CerebrasProvider {
        +base_url: str
        +api_key: str
        +available_models: List
    }

    class OpenRouterProvider {
        +base_url: str
        +api_key: str
        +available_models: List
    }

    class ChutesProvider {
        +base_url: str
        +api_key: str
        +available_models: List
    }

    class AIProviderManager {
        +providers: Dict
        +load_providers()
        +get_available_providers()
        +send_message()
        +send_message_streaming()
        +auto_send_message()
    }

    AIProvider <|-- OllamaProvider
    AIProvider <|-- CerebrasProvider
    AIProvider <|-- OpenRouterProvider
    AIProvider <|-- ChutesProvider
    AIProviderManager --> AIProvider
```

**Supported providers:**

| Provider | Base URL | Vision Support | Image Gen |
| --- | --- | --- | --- |
| Ollama | `http://127.0.0.1:11434` | No | No |
| Cerebras | `https://api.cerebras.ai/v1/chat/completions` | No | No |
| OpenRouter | `https://openrouter.ai/api/v1/chat/completions` | `moonshotai/kimi-k2.5` | Via Chutes |
| Chutes | `https://llm.chutes.ai/v1/chat/completions` | No | Yes |

**Ollama models:**

```markdown
smollm:360m, smollm2:360m, glm-4.6:cloud, qwen3-vl:235b-cloud,
qwen3-coder:480b-cloud, kimi-k2:1t-cloud, kimi-k2.5:cloud,
gpt-oss:120b-cloud, gpt-oss:20b-cloud, deepseek-v3.1:671b-cloud
```

**OpenRouter models (selected):**

```markdown
moonshotai/kimi-k2.5, anthropic/claude-3.5-haiku, openai/gpt-4o-mini,
deepseek-ai/DeepSeek-V3, Qwen/Qwen3-8B, meta-llama/llama-3.3-70b-instruct
```

---

## Tool System

The tool system has two execution modes:

1. **Standard tool calling** — OpenAI `function` call format (primary, v2.1+)
2. **Legacy** `/command` **text detection** — command-prefixed responses (fallback compat)

### `file tools/schemas.py` — Tool Schema Definitions

Declarative tool definitions using `ToolParam` and `ToolDefinition` dataclasses.

```python
@dataclass
class ToolParam:
    name: str
    description: str
    type: str = "string"
    required: bool = True
    default: Optional[str] = None

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: List[ToolParam]
    requires_session: bool = False
    is_terminal: bool = False   # skips second LLM pass on success
    category: str = "general"
```

### `file tools/registry.py` — Central Registry

Single source of truth for tool dispatch. Lazy-loads `TOOL_DEFINITIONS` from each tool module on first access.

**Key exports:**

- `get_tool_definitions()` — returns list of all registered `ToolDefinition` dicts
- `get_tool_definition(name)` — returns schema for a specific tool
- `execute_tool(name, arguments, session_id)` — dispatch and return markdown contract
- `format_tool_result()` — produces structured `GenerateResult(text, tool_calls)`
- `get_tool_role(name)` — maps tool name to DB role string

### Tool Dispatch Flow

```
flowchart TD
    A[LLM response] --> B{tool_calls present?}
    B -->|Yes| C[Structured function call]
    B -->|No| D{Legacy /command?}
    D -->|Yes| E[Text command detection]
    D -->|No| F[Plain text response]
    C --> G[execute_tool name, args]
    E --> G
    G --> H[Markdown contract]
    H --> I{Terminal tool?}
    I -->|Yes| J[Return result]
    I -->|No| K[Synthesis pass]
    K --> L[Final response]
    J --> L
```

**Dispatch priority:**

1. Structured `tool_calls[0]` from LLM → execute via registry → done
2. Legacy `/command` text detection → execute via registry → done
3. Plain text → return as-is

### Registered Tool Schemas

| Tool | Role | Params | Terminal |
| --- | --- | --- | --- |
| `image_generate` | `image_tools` | `prompt` (str, required) | ✅ |
| `request` | `request_tools` | `url` (str, required), `method` (str, optional) | ❌ |
| `memory_search` | `memory_search_tools` | `query` (str, required) | ❌ |
| `memory_store` | `memory_store_tools` | `fact` (str, required), `category` (str, optional) | ❌ |

### Markdown Contract Format

Tool results are stored in a \`\`\`\`html-details\
\` block:

```html
<details>
<summary>🔧 image_tools</summary>

```bash
Yuzu$ /imagine a cute cat
```

> Image generated successfully\
> Saved to: static/generated_images/xxx.png

```markdown
```

### Tool Modules

Each tool module exports a `TOOL_DEFINITION` dict alongside its `execute()` function:

| Module | Purpose |
| --- | --- |
|  | Image generation via Chutes API (HunYuan, Z-Turbo, Qwen) |
|  | Fetch public HTTPS endpoints with size/type validation |
|  | Persist semantic facts with LLM-guided categorization |
|  | Hybrid retrieval across semantic + episodic memories |
|  | Vision model routing and image caching (non-tool, helpers) |

---

## Memory System

The memory subsystem lives in `app/memory/` and provides long-term, structured memory with human-inspired retention dynamics.

```
flowchart LR
    A[User Message] --> B[messages table]
    B --> C[segmenter.py]
    C --> D[semantic_facts - dynamic - segments]
    B --> E[extractor.py]
    E --> F[semantic_facts - static]
    B --> E
    E --> G[semantic_facts - dynamic - episodic]
    D --> H[retrieval.py]
    F --> H
    G --> H
    H --> I[Context for LLM]
    I --> J[LLM Response]
    H --> K[review.py]
    K -.-> F
    K -.-> G
```

### Memory Layers

| Layer | `fact_type` | `metadata.source_table` | Purpose |
| --- | --- | --- | --- |
| **Semantic** | `static` | — | Stable facts as (entity, relation, target) triples |
| **Episodic** | `dynamic` | `episodic_memories` | Summarized interaction events with emotional weight |
| **Segments** | `dynamic` | `conversation_segments` | Chunked conversation windows for summarization |

### Unified `semantic_facts` Table

All memory types stored in a single PostgreSQL table with pgvector:

```sql
CREATE TABLE semantic_facts (
    id SERIAL PRIMARY KEY,
    session_id INTEGER,
    fact_type VARCHAR(20),  -- 'static' | 'dynamic'
    content TEXT,
    embedding VECTOR(4096),
    metadata JSONB,         -- confidence, importance, source_table, etc.
    created_at TIMESTAMP,
    last_accessed TIMESTAMP
);
```

### Retrieval Scoring (pgvector)

```sql
-- Hybrid search: vector distance + metadata scores
SELECT *, 
  (embedding <=> query_vector) * 0.6 + 
  (metadata->>'importance')::float * 0.2 + 
  (metadata->>'confidence')::float * 0.2 AS score
FROM semantic_facts
WHERE fact_type = 'static'
ORDER BY embedding <=> query_vector
LIMIT 15;
```

### FSRS-Inspired Retention

- Memory **stability** increases with access count
- **Importance** decays: `importance × exp(-hours/stability)`
- Frequently retrieved memories become **long-term anchors**
- Low-importance memories **naturally fade**

### Key Modules

| Module | Purpose |
| --- | --- |
|  | Unified CRUD over `semantic_facts` with pgvector search |
|  | SQL constants + query builders |
|  | Hybrid scoring retrieval pipeline |
|  | LLM-based semantic + episodic extraction |
|  | Background pipeline + batch segmentation |
|  | FSRS-style decay and reinforcement |
|  | Chutes API embedding client |

See `file memory/README.md` for full documentation.

---

## Multimodal System

### `file tools/multimodal.py`

Handles image processing for vision and generation:

```
flowchart TD
    A[User Message] --> B{Image detected?}
    B -->|Yes| C[Download to cache]
    B -->|No| D[Normal text processing]
    C --> E{Image type?}
    E -->|URL| F[Cache remote image]
    E -->|Upload| G[Use local path]
    F --> H[Base64 encode]
    G --> H
    H --> I[Format vision message]
    I --> J[moonshotai/kimi-k2.5]
    J --> K[Vision analysis]

    L[imagine command] --> M[Chutes API]
    M --> N[Save to static/generated_images/]
    N --> O[Return path in contract]
```

**Vision pipeline:**

1. Extract image URLs/paths from message markdown
2. Download remote images to `static/image_cache/`
3. Encode as base64 data URI
4. Route to `moonshotai/kimi-k2.5` via OpenRouter
5. Attach vision response to conversation

**Image generation pipeline:**

1. Detect `/imagine` command or image generation keywords
2. Call Chutes image API
3. Save result to `static/generated_images/`
4. Return markdown with image path
5. Second LLM pass to describe generated image

---

## Encryption

### `file encryption.py`

ChaCha20-Poly1305 encryption for API keys at rest:

- **API keys**: Always encrypted
- **Messages**: Encryption disabled by default (configurable)
- Key derivation from master key in `encryption.key`
- Fallback to plaintext if decryption fails

### `file key_manager.py`

Master key lifecycle management:

- Key generation on first run
- Secure key storage
- Key rotation support

---

## Session Management

```
stateDiagram-v2
    [*] --> ActiveSession
    ActiveSession --> MessageExchange: user sends message
    MessageExchange --> MemoryPipeline: trigger extraction
    MemoryPipeline --> Retrieval: context building
    Retrieval --> LLM: inject memory context
    LLM --> Response: generate reply
    Response --> MessageExchange: loop
    ActiveSession --> EndSession: /exit or timeout
    EndSession --> SessionSummary: update memory
    SessionSummary --> [*]
```

On session start:

1. Run FSRS decay on existing memories
2. Segment unsegmented messages
3. Extract semantic + episodic memories
4. Initialize session context

---

## Configuration

### Profile Settings (stored in `profiles` table)

```python
{
    "display_name": str,      # User's display name
    "partner_name": str,      # AI companion name
    "affection": int,         # 0-100 affection level
    "theme": str,             # UI theme
    "memory": {               # Player profile memory
        "player_summary": str,
        "key_facts": {
            "likes": [],
            "dislikes": [],
            "personality_traits": []
        }
    },
    "providers_config": {
        "preferred_provider": str,
        "preferred_model": str,
        "streaming_enabled": bool
    }
}
```

### API Key Management

API keys are stored encrypted in `api_keys` table:

- `cerebras` — Cerebras API key
- `chutes` — Chutes API key
- `openrouter` — OpenRouter API key

---

## Workflow: Message Processing

```
sequenceDiagram
    participant U as User
    participant A as app.py
    participant M as Multimodal
    participant T as Tools/Registry
    participant P as Providers
    participant D as Database

    U->>A: "Hello! /imagine a cat"
    A->>M: detect_images()
    M-->>A: no images
    A->>A: detect_command()
    A->>T: execute_tool("imagine", {prompt})
    T->>P: generate_image()
    P-->>T: image path
    T-->>A: markdown contract
    A->>A: generate_ai_response()
    A->>P: send_message()
    P-->>A: text response
    A->>D: save messages
    A-->>U: combined response
```

---

## Dependencies

Based on actual imports in the codebase:

```markdown
# Core Dependencies
psycopg[binary,pool]>=3.1   # PostgreSQL adapter (psycopg v3) + pgvector
pycryptodome>=3.20.0       # ChaCha20-Poly1305 encryption for API keys
python-dotenv>=1.0.0       # Environment variable loading

# Web Framework (FastAPI)
fastapi>=0.115.0           # Modern async web framework
uvicorn[standard]>=0.30.0  # ASGI server
pydantic>=2.8.0            # Data validation
python-multipart>=0.0.9   # File uploads
Jinja2>=3.1.0              # Template engine

# Terminal UI
rich>=13.0.0               # Terminal formatting
prompt-toolkit>=3.0.0      # Advanced input with history

# Networking
requests>=2.33.0           # HTTP requests for AI providers

# Development (optional)
black>=23.0.0              # Code formatting
pytest>=7.0.0              # Testing framework
mypy>=1.0.0                # Type checking
```

---

## Architecture Principles

1. **Single entry point** — `handle_user_message()` is the only gateway for user messages
2. **Tool isolation** — all tools go through `execute_tool()` with markdown contracts
3. **Memory-first** — memory pipeline runs on every session start and periodically
4. **Provider abstraction** — `AIProviderManager` hides provider differences
5. **Safe migrations** — database never drops tables, only adds columns
6. **No heuristic detection** — LLM determines responses, not hardcoded rules