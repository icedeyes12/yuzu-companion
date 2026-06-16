# FILE: tests/test_commands.py
# DESCRIPTION: Tests for app.commands.
#              As of Phase E, the LLM-side <command>...</command> parser has been
#              removed in favour of native OpenAI tool_calls. This module now
#              only tests the narrow direct-user-input helpers and the
#              image-path post-processing helpers that survived the cut-down.

from __future__ import annotations

from app.commands import (
    _parse_user_fastpath_command,
    _resolve_user_alias,
    extract_markdown_image_path,
    is_markdown_image_shortcut,
    parse_image_path,
)


class TestParseUserFastpathCommand:
    """Tests for the narrowly-scoped direct user input parser."""

    def test_empty_input(self):
        assert _parse_user_fastpath_command("") is None
        assert _parse_user_fastpath_command("   ") is None

    def test_slash_prefix(self):
        parsed = _parse_user_fastpath_command("/imagine a cat")
        assert parsed is not None
        assert parsed["command"] == "imagine"
        assert parsed["args"] == "a cat"
        assert parsed["full_command"] == "/imagine a cat"

    def test_no_slash_prefix(self):
        parsed = _parse_user_fastpath_command("imagine a cat")
        assert parsed is not None
        assert parsed["command"] == "imagine"
        assert parsed["args"] == "a cat"

    def test_no_args(self):
        parsed = _parse_user_fastpath_command("/imagine")
        assert parsed is not None
        assert parsed["command"] == "imagine"
        assert parsed["args"] == ""


class TestResolveUserAlias:
    """Tests for the alias resolver used by direct user input."""

    def test_imagine_alias(self):
        assert _resolve_user_alias("imagine") == "image_generate"

    def test_request_alias(self):
        assert _resolve_user_alias("request") == "http_request"

    def test_ask_rei_alias(self):
        assert _resolve_user_alias("ask-rei") == "ask_rei"

    def test_passthrough_unknown(self):
        assert _resolve_user_alias("bash") == "bash"


class TestParseImagePath:
    """Tests for image path extraction from tool result markdown."""

    def test_extracts_generated_image_src(self):
        contract = (
            "<details><summary>shell_tools</summary>"
            '<img src="static/generated_images/abc.png" /></details>'
        )
        assert parse_image_path(contract) == "static/generated_images/abc.png"

    def test_returns_none_when_no_image(self):
        assert parse_image_path("<details>no image</details>") is None
        assert parse_image_path("") is None

    def test_rejects_absolute_paths(self):
        contract = '<img src="/static/generated_images/abc.png" />'
        assert parse_image_path(contract) is None

    def test_rejects_traversal(self):
        contract = '<img src="static/../etc/passwd" />'
        assert parse_image_path(contract) is None


class TestIsMarkdownImageShortcut:
    """Tests for the markdown-image-shortcut guard."""

    def test_returns_true_for_static_path(self):
        text = "look ![alt](static/generated_images/foo.png)"
        assert is_markdown_image_shortcut(text) is True

    def test_returns_true_for_uploads_path(self):
        text = "look ![alt](uploads/foo.png)"
        assert is_markdown_image_shortcut(text) is True

    def test_returns_false_for_external_url(self):
        text = "look ![alt](https://example.com/foo.png)"
        assert is_markdown_image_shortcut(text) is False

    def test_returns_false_for_empty(self):
        assert is_markdown_image_shortcut("") is False
        assert is_markdown_image_shortcut(None) is False


class TestExtractMarkdownImagePath:
    """Tests for the markdown image path extractor."""

    def test_extracts_first_image(self):
        text = "first ![a](static/a.png) then ![b](static/b.png)"
        assert extract_markdown_image_path(text) == "static/a.png"

    def test_returns_none_when_no_image(self):
        assert extract_markdown_image_path("no image here") is None
        assert extract_markdown_image_path("") is None
