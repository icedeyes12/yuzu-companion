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

    def test_strips_standard_tool_result(self):
        from app import _strip_tool_markdown
        raw = '🔧 TOOL RESULT — WEB_SEARCH\n\n{"results": []}\n\n---'
        assert _strip_tool_markdown(raw) == '{"results": []}'

    def test_strips_tool_error(self):
        from app import _strip_tool_markdown
        raw = '🔧 TOOL ERROR — WEATHER\n\nError: timeout\n\n---'
        assert _strip_tool_markdown(raw) == 'Error: timeout'

    def test_strips_double_wrapped(self):
        from app import _strip_tool_markdown
        inner = '🔧 TOOL RESULT — WEB_SEARCH\n\n{"ok":true}\n\n---'
        outer = f'🔧 TOOL RESULT — WEB_SEARCH\n\n{inner}\n\n---'
        assert _strip_tool_markdown(outer) == '{"ok":true}'

    def test_strips_code_fences(self):
        from app import _strip_tool_markdown
        raw = '🔧 TOOL RESULT — MEMORY_SQL\n\n```bash\nSELECT 1\n```\n\n---'
        result = _strip_tool_markdown(raw)
        assert '```' not in result
        assert 'SELECT 1' in result

    def test_strips_executor_prefix(self):
        from app import _strip_tool_markdown
        raw = '🔧 TOOL RESULT — REQUEST\n\nExecutor$ /request https://example.com\nOK\n\n---'
        result = _strip_tool_markdown(raw)
        assert 'Executor$' not in result
        assert '/request https://example.com' in result

    def test_strips_blockquote_markers(self):
        from app import _strip_tool_markdown
        raw = '🔧 TOOL RESULT — WEB_SEARCH\n\n> line one\n> line two\n\n---'
        result = _strip_tool_markdown(raw)
        assert result == 'line one\nline two'

    def test_returns_none_for_none(self):
        from app import _strip_tool_markdown
        assert _strip_tool_markdown(None) is None

    def test_returns_empty_string(self):
        from app import _strip_tool_markdown
        assert _strip_tool_markdown('') == ''

    def test_returns_empty_for_whitespace(self):
        from app import _strip_tool_markdown
        assert _strip_tool_markdown('   ') == ''

    def test_passthrough_plain_text(self):
        from app import _strip_tool_markdown
        plain = 'Just some text without markers'
        assert _strip_tool_markdown(plain) == plain


# ---------------------------------------------------------------------------
# 2. Projection model – context builder
# ---------------------------------------------------------------------------

class TestProjectionModel:
    """Tool results must be projected as assistant (command) + user (result)."""

    def test_no_tool_emoji_in_llm_payload(self):
        from database import Database, ALL_TOOL_ROLES
        from app import _build_generation_context

        session_id = Database.create_session("test-projection-clean")
        Database.switch_session(session_id)
        Database.add_tool_result("weather", '{"temp": 20}', session_id=session_id)

        profile = Database.get_profile()
        messages = _build_generation_context(profile, session_id, "terminal")

        for msg in messages:
            assert msg['role'] not in ALL_TOOL_ROLES, \
                f"Raw tool role '{msg['role']}' leaked"
            assert '🔧' not in msg.get('content', ''), \
                f"Tool emoji leaked into LLM payload: {msg['content'][:80]}"

    def test_tool_results_split_into_two_messages(self):
        from database import Database
        from app import _build_generation_context

        session_id = Database.create_session("test-projection-split")
        Database.switch_session(session_id)
        Database.add_tool_result("web_search", '{"results":[]}', session_id=session_id)

        profile = Database.get_profile()
        messages = _build_generation_context(profile, session_id, "terminal")

        # Find the assistant command message and its following user result
        command_found = False
        result_found = False
        for i, msg in enumerate(messages):
            if msg['role'] == 'assistant' and msg['content'] == '/web_search':
                command_found = True
                # Next message should be user with the raw result
                if i + 1 < len(messages):
                    nxt = messages[i + 1]
                    if nxt['role'] == 'user' and '{"results":[]}' in nxt['content']:
                        result_found = True

        assert command_found, "Tool command not projected as assistant message"
        assert result_found, "Tool result not projected as user message after command"

    def test_projection_preserves_raw_result(self):
        from database import Database
        from app import _build_generation_context

        session_id = Database.create_session("test-projection-raw")
        Database.switch_session(session_id)
        raw = '{"image_path": "static/generated_images/test.png"}'
        Database.add_tool_result("imagine", raw, session_id=session_id)

        profile = Database.get_profile()
        messages = _build_generation_context(profile, session_id, "terminal")

        result_msgs = [m for m in messages if m['role'] == 'user' and raw in m['content']]
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
    """_extract_tool_command must return the correct slash command."""

    def test_web_search(self):
        from app import _extract_tool_command
        raw = '🔧 TOOL RESULT — WEB_SEARCH\n\n{}\n\n---'
        assert _extract_tool_command(raw) == '/web_search'

    def test_imagine(self):
        from app import _extract_tool_command
        raw = '🔧 TOOL RESULT — IMAGINE\n\n{}\n\n---'
        assert _extract_tool_command(raw) == '/imagine'

    def test_request(self):
        from app import _extract_tool_command
        raw = '🔧 TOOL RESULT — REQUEST\n\n{}\n\n---'
        assert _extract_tool_command(raw) == '/request'

    def test_http_request(self):
        from app import _extract_tool_command
        raw = '🔧 TOOL RESULT — HTTP_REQUEST\n\n{}\n\n---'
        assert _extract_tool_command(raw) == '/request'

    def test_error_format(self):
        from app import _extract_tool_command
        raw = '🔧 TOOL ERROR — WEATHER\n\nError\n\n---'
        assert _extract_tool_command(raw) == '/weather'

    def test_none_input(self):
        from app import _extract_tool_command
        assert _extract_tool_command(None) is None

    def test_plain_text(self):
        from app import _extract_tool_command
        assert _extract_tool_command("just text") is None


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
