---
name: fastapi-textual-architecture
description: Conventions for FastAPI endpoints and Textual CLI code in yuzu-companion. Use when editing app/api/ or cli/.
compatibility: Created for Zo Computer
metadata:
  author: yuzu.zo.computer
---

# FastAPI + Textual Architecture Conventions

## Scope
Covers the backend route layer in `file 'app/api/'` and the Textual TUI client in `file 'cli/'`. About route shape, thin endpoints, streaming, and the CLI presentation boundary. Does not override the base constitutions.

## 1. FastAPI Entrypoint and Router Aggregation
- The FastAPI app is instantiated in `file 'main.py'` (`app = FastAPI(...)` with a `lifespan` that manages the DB pool). `file 'app/web.py'` does **not** exist despite older docs referencing it.
- `file 'app/api/main.py'` is the router aggregator: a single `APIRouter()` that `include_router`s each endpoint module plus the static router.
- Routes live in `file 'app/api/endpoints/'` (one file per domain: `chat.py`, `sessions.py`, `profile.py`, `memory.py`, `stream.py`).

## 2. Endpoint Conventions
- Each endpoint module declares `router = APIRouter(...)` and is included by `file 'app/api/main.py'`.
- Prefix style is **mixed by design**: domain routers that own a path namespace use `prefix="..."` and `tags=[...]` (e.g. `file 'app/api/endpoints/stream.py'` uses `prefix="/stream", tags=["stream"]`); the chat router uses `tags=["chat"]` with full paths in decorators. Match the convention already used in the file you are editing; do not retroactively normalize.
- Keep endpoint functions thin. Offload work to `file 'app/services/'` (`ChatService`, `SessionService`, `MemoryService`, `ConfigService`). Endpoints should parse input, call a service, and shape the response.
- Use Pydantic `BaseModel` for structured JSON bodies; use `Form` / `File` / `UploadFile` for multipart. The streaming endpoint supports both JSON and form payloads — preserve that dual handling if you touch it.
- For SSE, return `StreamingResponse(generator, media_type="text/event-stream")`. The SSE line format is `data: {"chunk": "..."}\n\n`.
- Exception handling: log details with `get_logger(__name__)`, return a **generic** message to the client. Never echo `str(e)` to the user (the streaming endpoint in `file 'app/api/endpoints/chat.py'` is the correct pattern; the non-streaming `send_message` endpoint currently leaks `str(e)` and should not be used as a template).

## 3. Service Layer
- `file 'app/services/'` holds the orchestration the endpoints delegate to. Services expose a **dual sync + async** API (e.g. `SessionService.start_session` and `start_session_async`). Prefer the `_async` variants from endpoints (endpoints run in the event loop).
- Endpoints may import `file 'app/orchestrator.py'` directly only for thin legacy bridges; new logic goes through a service.

## 4. Textual CLI Boundaries
- The CLI is a **thin HTTP client only**. `file 'cli/client.py'` (`YuzuClient`) uses `httpx.AsyncClient` and never imports `app.db`, services, or models. Keep that boundary absolute.
- `file 'cli/app.py'` (`YuzuTUI(App)`) declares `CSS_PATH = "styles/app.tcss"`, `BINDINGS`, a `compose()` layout (`Header` + `Horizontal(#main-layout)` with `SessionList` sidebar + `Container(#chat-container)` holding `ChatLog` + `InputBox` + `Footer`), and widget classes in `file 'cli/widgets/'` (`ChatLog`, `InputBox`, `SessionList`).
- Non-blocking work: schedule async work with `asyncio.create_task(...)` and push UI updates back to the main thread with `self.call_later(...)`. Never mutate widgets directly from an `asyncio.create_task` callback.
- Inter-widget communication uses Textual messages (`InputBox.MessageSubmitted`, `SessionList.SessionSelected`). Add new events as message classes on the emitting widget.
- Responsive layout: detect `shutil.get_terminal_size().columns`; at `>= 80` columns add the `desktop` CSS class to `#main-layout`, `SessionList`, and `#chat-container` (sidebar always visible); below 80 keep mobile default (sidebar hidden, toggled via `ctrl+s`). CSS lives in `file 'cli/styles/app.tcss'`.

## Anti-Patterns
- Do not import `Database` or `app.db` into `file 'cli/'`.
- Do not put business logic in endpoint handlers; route through a service.
- Do not leak exception strings to API clients.
- Do not add a new streaming protocol; SSE via `StreamingResponse` is the only path.
- Do not bypass the service layer by calling the orchestrator from an endpoint for new features (the `/generate_image` endpoint's direct `handle_user_message("/imagine ...")` call is a legacy `/command` escape hatch, not a pattern to copy).
