"""Tests for the consolidated orchestration review changes.

Covers:
  1. Tool result projection – markdown stripping
  2. Retry discipline – no retry on None/empty
  3. Length handling – finish_reason == 'length' returns partial content with ...(length)
  4. HTTP tool integrity – /request maps to {"url": ...}
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# 1. _strip_tool_markdown
# ---------------------------------------------------------------------------

class TestStripToolMarkdown:
    """Verify markdown wrappers are stripped cleanly for LLM projection."""

    # --- <details> contract ---

    def test_strips_details_image(self):
        from app import _strip_tool_markdown
        raw = (
            '<details>\n<summary>🔧 image_tools</summary>\n\n'
            '```bash\nYuzuki Aihara$ /imagine test prompt\n```\n\n'
            '> <img src="static/generated_images/test.png" alt="Generated Image">\n\n'
            '</details>'
        )
        result = _strip_tool_markdown(raw)
        assert '<details>' not in result
        assert '<summary>' not in result
        assert '```' not in result
        assert 'Yuzuki Aihara$' not in result
        assert '<img src="static/generated_images/test.png"' in result

    def test_strips_details_request(self):
        from app import _strip_tool_markdown
        raw = (
            '<details>\n<summary>🔧 request_tools</summary>\n\n'
            '```bash\nYuzuki Aihara$ /request\n```\n\n'
            '> Error: No URL provided\n\n'
            '</details>'
        )
        result = _strip_tool_markdown(raw)
        assert result == 'Error: No URL provided'

    def test_strips_details_web_search(self):
        from app import _strip_tool_markdown
        raw = (
            '<details>\n<summary>🔧 web_search_tools</summary>\n\n'
            '```bash\nYuzuki Aihara$ /web_search Python\n```\n\n'
            '> {"results": []}\n\n'
            '</details>'
        )
        result = _strip_tool_markdown(raw)
        assert result == '{"results": []}'

    # --- Non-<details> content returned as-is ---

    def test_passthrough_plain_text(self):
        from app import _strip_tool_markdown
        plain = 'Just some text without markers'
        assert _strip_tool_markdown(plain) == plain

    def test_passthrough_plain_path(self):
        from app import _strip_tool_markdown
        path = 'static/generated_images/test.png'
        assert _strip_tool_markdown(path) == path

    # --- Edge cases ---

    def test_returns_none_for_none(self):
        from app import _strip_tool_markdown
        assert _strip_tool_markdown(None) is None

    def test_returns_empty_string(self):
        from app import _strip_tool_markdown
        assert _strip_tool_markdown('') == ''

    def test_returns_empty_for_whitespace(self):
        from app import _strip_tool_markdown
        assert _strip_tool_markdown('   ') == ''


# ---------------------------------------------------------------------------
# 2. Projection model – context builder
# ---------------------------------------------------------------------------

class TestProjectionModel:
    """Tool results must be projected as assistant (command) + *_tools (result)."""

    def test_tool_emoji_not_in_content(self):
        from database import Database
        from app import _build_generation_context

        session_id = Database.create_session("test-projection-clean")
        Database.switch_session(session_id)
        Database.add_tool_result("weather", '{"temp": 20}', session_id=session_id)

        profile = Database.get_profile()
        messages = _build_generation_context(profile, session_id, "terminal")

        for msg in messages:
            assert '🔧' not in msg.get('content', ''), \
                f"Tool emoji leaked into LLM payload: {msg['content'][:80]}"

    def test_tool_results_split_into_two_messages(self):
        from database import Database
        from app import _build_generation_context

        session_id = Database.create_session("test-projection-split")
        Database.switch_session(session_id)
        Database.add_tool_result("web_search", '{"results":[]}', session_id=session_id,
                                 full_command="/web_search test query")

        profile = Database.get_profile()
        messages = _build_generation_context(profile, session_id, "terminal")

        # Find the assistant command message and its following *_tools result
        command_found = False
        result_found = False
        for i, msg in enumerate(messages):
            if msg['role'] == 'assistant' and '/web_search' in msg['content']:
                command_found = True
                # Next message should be web_search_tools with the raw result
                if i + 1 < len(messages):
                    nxt = messages[i + 1]
                    if nxt['role'] == 'web_search_tools' and '{"results":[]}' in nxt['content']:
                        result_found = True

        assert command_found, "Tool command not projected as assistant message"
        assert result_found, "Tool result not projected as *_tools message after command"

    def test_projection_preserves_raw_result(self):
        from database import Database
        from app import _build_generation_context

        session_id = Database.create_session("test-projection-raw")
        Database.switch_session(session_id)
        raw = '{"image_path": "static/generated_images/test.png"}'
        Database.add_tool_result("imagine", raw, session_id=session_id,
                                 full_command="/imagine a cute cat")

        profile = Database.get_profile()
        messages = _build_generation_context(profile, session_id, "terminal")

        result_msgs = [m for m in messages if m['role'] == 'image_tools' and raw in m['content']]
        assert len(result_msgs) >= 1, "Raw result not preserved in projection"


# ---------------------------------------------------------------------------
# 3. Retry discipline
# ---------------------------------------------------------------------------

class TestRetryDiscipline:
    """Retry on null response only; no retry on empty string or partial content."""

    def test_retry_once_on_none_non_streaming(self, monkeypatch):
        import app

        session_id = _create_test_session("test-retry-none")

        class CountingManager:
            def __init__(self):
                self.calls = 0
            def send_message(self, *a, **kw):
                self.calls += 1
                return None  # Simulate provider failure

        mgr = CountingManager()
        monkeypatch.setattr(app, "get_ai_manager", lambda: mgr)

        result = app.generate_ai_response(
            _minimal_profile(), "hello", interface="terminal", session_id=session_id
        )

        # Null response triggers exactly one retry (2 total calls)
        assert mgr.calls == 2, f"Expected 2 calls (1 + retry), got {mgr.calls}"
        assert "failed" in result.lower() or "couldn't" in result.lower()

    def test_no_retry_on_empty_non_streaming(self, monkeypatch):
        import app

        session_id = _create_test_session("test-retry-empty")

        class CountingManager:
            def __init__(self):
                self.calls = 0
            def send_message(self, *a, **kw):
                self.calls += 1
                return ""  # Empty string — not a transport error

        mgr = CountingManager()
        monkeypatch.setattr(app, "get_ai_manager", lambda: mgr)

        result = app.generate_ai_response(
            _minimal_profile(), "hello", interface="terminal", session_id=session_id
        )

        assert mgr.calls == 1, f"Expected 1 call, got {mgr.calls}"

    def test_retry_once_on_none_streaming(self, monkeypatch):
        import app

        session_id = _create_test_session("test-retry-stream-none")

        class CountingManager:
            def __init__(self):
                self.calls = 0
            def send_message(self, *a, **kw):
                self.calls += 1
                return None

        mgr = CountingManager()
        monkeypatch.setattr(app, "get_ai_manager", lambda: mgr)

        # Consume the generator
        chunks = list(app.generate_ai_response_streaming(
            _minimal_profile(), "hello", interface="terminal", session_id=session_id
        ))

        # Null response triggers exactly one retry (2 total calls)
        assert mgr.calls == 2, f"Expected 2 calls (1 + retry), got {mgr.calls}"


# ---------------------------------------------------------------------------
# 4. Length handling – finish_reason == "length"
# ---------------------------------------------------------------------------

class TestLengthHandling:
    """Partial content with finish_reason 'length' must be returned with suffix."""

    def test_openrouter_length_suffix(self):
        from providers import OpenRouterProvider
        import requests as _req
        from unittest.mock import patch, MagicMock

        provider = OpenRouterProvider.__new__(OpenRouterProvider)
        provider.api_key = "test-key"
        provider.available_models = ["test-model"]
        provider.name = "openrouter"
        provider.base_url = "https://openrouter.ai/api/v1/chat/completions"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {"content": "partial answer here"},
                "finish_reason": "length"
            }]
        }

        with patch.object(_req, 'post', return_value=mock_resp):
            result = provider.send_message(
                [{"role": "user", "content": "hi"}], "test-model"
            )

        assert result.endswith("...(length)"), f"Expected ...(length) suffix, got: {result}"
        assert "partial answer here" in result

    def test_openrouter_stop_no_suffix(self):
        from providers import OpenRouterProvider
        import requests as _req
        from unittest.mock import patch, MagicMock

        provider = OpenRouterProvider.__new__(OpenRouterProvider)
        provider.api_key = "test-key"
        provider.available_models = ["test-model"]
        provider.name = "openrouter"
        provider.base_url = "https://openrouter.ai/api/v1/chat/completions"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {"content": "full answer"},
                "finish_reason": "stop"
            }]
        }

        with patch.object(_req, 'post', return_value=mock_resp):
            result = provider.send_message(
                [{"role": "user", "content": "hi"}], "test-model"
            )

        assert not result.endswith("...(length)")
        assert result == "full answer"

    def test_chutes_length_suffix(self):
        from providers import ChutesProvider
        import requests as _req
        from unittest.mock import patch, MagicMock

        provider = ChutesProvider.__new__(ChutesProvider)
        provider.api_key = "test-key"
        provider.available_models = ["test-model"]
        provider.name = "chutes"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {"content": "truncated"},
                "finish_reason": "length"
            }]
        }

        with patch.object(_req, 'post', return_value=mock_resp):
            result = provider.send_message(
                [{"role": "user", "content": "hi"}], "test-model"
            )

        assert result.endswith("...(length)")


# ---------------------------------------------------------------------------
# 5. HTTP tool integrity – /request argument mapping
# ---------------------------------------------------------------------------

class TestRequestToolMapping:
    """/request must map to {"url": ...} not {"query": ...}."""

    def test_request_command_maps_url(self):
        from app import _detect_command, _execute_command_tool

        cmd = _detect_command("/request https://example.com")
        assert cmd is not None
        assert cmd["command"] == "request"
        assert cmd["args"] == "https://example.com"

    def test_request_tool_arg_structure(self, monkeypatch):
        """Verify that _execute_command_tool passes {"url": ...} for /request."""
        import app

        captured_args = {}

        def fake_execute(tool_name, args, session_id=None):
            captured_args['tool'] = tool_name
            captured_args['args'] = args
            return json.dumps({"status": 200, "body": "OK"})

        monkeypatch.setattr(app, "execute_tool", fake_execute)

        cmd_info = {
            "command": "request",
            "args": "https://example.com",
            "remaining_text": "",
            "full_command": "/request https://example.com"
        }
        _execute_command_tool = app._execute_command_tool
        _execute_command_tool(cmd_info, session_id=1)

        assert captured_args['args'] == {"url": "https://example.com"}, \
            f"Expected url mapping, got {captured_args['args']}"


# ---------------------------------------------------------------------------
# 6. Schema exclusion – http_request must not be in provider schemas
# ---------------------------------------------------------------------------

class TestSchemaExclusion:
    """http_request tool must not appear in provider payload schemas."""

    def test_http_request_excluded_from_schemas(self):
        from tools.registry import get_tool_schemas
        schemas = get_tool_schemas()
        names = [s['function']['name'] for s in schemas]
        assert 'http_request' not in names, \
            "http_request must not be injected into provider schemas"

    def test_other_tools_still_present(self):
        from tools.registry import get_tool_schemas
        schemas = get_tool_schemas()
        names = [s['function']['name'] for s in schemas]
        for tool in ['web_search', 'weather', 'memory_sql', 'image_generate']:
            assert tool in names, f"Expected {tool} in schemas"


# ---------------------------------------------------------------------------
# 7. Tool command extraction
# ---------------------------------------------------------------------------

class TestToolCommandExtraction:
    """_extract_tool_command must return the correct slash command from <details> contract."""

    # --- <details> contract ---

    def test_details_image_command(self):
        from app import _extract_tool_command
        raw = (
            '<details>\n<summary>🔧 image_tools</summary>\n\n'
            '```bash\nYuzuki Aihara$ /imagine test prompt\n```\n\n'
            '> <img src="test.png">\n\n</details>'
        )
        assert _extract_tool_command(raw) == '/imagine test prompt'

    def test_details_request_command(self):
        from app import _extract_tool_command
        raw = (
            '<details>\n<summary>🔧 request_tools</summary>\n\n'
            '```bash\nYuzuki Aihara$ /request https://example.com\n```\n\n'
            '> {"ok":true}\n\n</details>'
        )
        assert _extract_tool_command(raw) == '/request https://example.com'

    def test_details_web_search_command(self):
        from app import _extract_tool_command
        raw = (
            '<details>\n<summary>🔧 web_search_tools</summary>\n\n'
            '```bash\nYuzuki Aihara$ /web_search Python programming\n```\n\n'
            '> {"results":[]}\n\n</details>'
        )
        assert _extract_tool_command(raw) == '/web_search Python programming'

    def test_details_weather_command(self):
        from app import _extract_tool_command
        raw = (
            '<details>\n<summary>🔧 weather_tools</summary>\n\n'
            '```bash\nYuzuki Aihara$ /weather Tokyo\n```\n\n'
            '> {"temp": 20}\n\n</details>'
        )
        assert _extract_tool_command(raw) == '/weather Tokyo'

    # --- Non-<details> content returns None ---

    def test_legacy_format_returns_none(self):
        from app import _extract_tool_command
        raw = '🔧 TOOL RESULT — WEB_SEARCH\n\n{}\n\n---'
        assert _extract_tool_command(raw) is None

    def test_none_input(self):
        from app import _extract_tool_command
        assert _extract_tool_command(None) is None

    def test_plain_text(self):
        from app import _extract_tool_command
        assert _extract_tool_command("just text") is None


# ---------------------------------------------------------------------------
# 8. Rendering contract enforcement
# ---------------------------------------------------------------------------

class TestRenderingContract:
    """_execute_command_tool must return <details> contract — not legacy format."""

    def test_execute_command_returns_details_contract(self, monkeypatch):
        """_execute_command_tool must return a <details> contract."""
        import app
        monkeypatch.setattr(app, "execute_tool", lambda *a, **kw: '{"results":[]}')

        cmd_info = {
            "command": "web_search",
            "args": "test query",
            "remaining_text": "",
            "full_command": "/web_search test query"
        }
        result = app._execute_command_tool(cmd_info, session_id=1)
        assert result.strip().startswith("<details>"), \
            f"Expected <details> contract, got: {result[:80]}"
        assert result.strip().endswith("</details>"), \
            f"Expected </details> at end, got: {result[-30:]}"

    def test_execute_command_no_legacy_emoji(self, monkeypatch):
        """No 🔧 TOOL RESULT header in return value."""
        import app
        monkeypatch.setattr(app, "execute_tool", lambda *a, **kw: '{"ok":true}')

        cmd_info = {
            "command": "weather",
            "args": "Tokyo",
            "remaining_text": "",
            "full_command": "/weather Tokyo"
        }
        result = app._execute_command_tool(cmd_info, session_id=1)
        assert "🔧 TOOL RESULT —" not in result
        assert "🔧 TOOL ERROR —" not in result

    def test_error_returns_details_contract(self, monkeypatch):
        """Error results must also use <details> contract."""
        import app

        def failing_tool(*a, **kw):
            raise ValueError("connection timeout")

        monkeypatch.setattr(app, "execute_tool", failing_tool)

        cmd_info = {
            "command": "web_search",
            "args": "test",
            "remaining_text": "",
            "full_command": "/web_search test"
        }
        result = app._execute_command_tool(cmd_info, session_id=1)
        assert result.strip().startswith("<details>")
        assert "connection timeout" in result
        assert "🔧 TOOL ERROR —" not in result

    def test_build_tool_contract_is_shared(self):
        """build_tool_contract is importable and produces <details> output."""
        from database import build_tool_contract
        contract = build_tool_contract("weather", '{"temp": 20}',
                                       full_command="/weather Tokyo",
                                       partner_name="TestBot")
        assert contract.startswith("<details>")
        assert "</details>" in contract
        assert "TestBot$ /weather Tokyo" in contract
        assert '> {"temp": 20}' in contract

    def test_rendered_output_matches_db(self, monkeypatch):
        """Rendered output and DB content must be identical."""
        import app
        from database import Database, get_db_session, Message

        monkeypatch.setattr(app, "execute_tool", lambda *a, **kw: '{"data":"ok"}')

        sid = Database.create_session("test-render-match-db")
        Database.switch_session(sid)

        cmd_info = {
            "command": "web_search",
            "args": "test",
            "remaining_text": "",
            "full_command": "/web_search test"
        }
        rendered = app._execute_command_tool(cmd_info, session_id=sid)
        Database.add_tool_result("web_search", rendered, session_id=sid,
                                 full_command="/web_search test")

        with get_db_session() as session:
            msg = session.query(Message).filter(
                Message.session_id == sid,
                Message.role == 'web_search_tools'
            ).order_by(Message.id.desc()).first()
            assert msg is not None
            assert rendered.strip() == msg.content.strip(), \
                "Rendered output differs from DB content"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_session(name):
    from database import Database
    sid = Database.create_session(name)
    Database.switch_session(sid)
    return sid

def _minimal_profile():
    """Return a minimal profile dict for testing."""
    from database import Database
    return Database.get_profile()
