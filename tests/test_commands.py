# FILE: tests/test_commands.py
# DESCRIPTION: Pure-function tests for app.commands image-path helpers.
#              Legacy <command> parser tests removed — native tool_calls is the
#              only tool invocation mechanism now.

from __future__ import annotations

from app.commands import parse_image_path


class TestParseImagePath:
    """Tests for image path extraction from tool results."""

    def test_extracts_generated_image_src(self):
        contract = (
            "<details><summary>shell_tools</summary>"
            '<img src="static/generated_images/abc.png" /></details>'
        )
        assert parse_image_path(contract) == "static/generated_images/abc.png"

    def test_returns_none_when_no_image(self):
        assert parse_image_path("<details>no image</details>") is None
        assert parse_image_path("") is None

    def test_rejects_path_traversal(self):
        assert parse_image_path('src="static/../../etc/passwd.png"') is None
        assert parse_image_path('src="/etc/passwd.png"') is None

    def test_rejects_non_image_extensions(self):
        assert parse_image_path('src="static/generated_images/file.txt"') is None

    def test_accepts_valid_extensions(self):
        for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            path = f"static/generated_images/test{ext}"
            assert parse_image_path(f'src="{path}"') == path
