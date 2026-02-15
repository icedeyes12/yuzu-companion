"""Tests for terminal_visual module."""

import sys
import os
import unittest
from unittest.mock import patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terminal_visual import preview_image_in_terminal, extract_image_path_from_markdown


class TestPreviewImageInTerminal(unittest.TestCase):
    """Tests for preview_image_in_terminal()."""

    @patch("terminal_visual.subprocess.run")
    @patch("terminal_visual.os.path.isfile", return_value=True)
    @patch("terminal_visual.shutil.which", return_value="/usr/bin/timg")
    def test_calls_timg_when_available(self, mock_which, mock_isfile, mock_run):
        preview_image_in_terminal("/tmp/test.png")
        mock_which.assert_called_once_with("timg")
        mock_isfile.assert_called_once_with("/tmp/test.png")
        mock_run.assert_called_once_with(["timg", "-g", "80x40", "/tmp/test.png"])

    @patch("terminal_visual.subprocess.run")
    @patch("terminal_visual.shutil.which", return_value=None)
    def test_skips_when_timg_not_installed(self, mock_which, mock_run):
        preview_image_in_terminal("/tmp/test.png")
        mock_run.assert_not_called()

    @patch("terminal_visual.subprocess.run")
    @patch("terminal_visual.os.path.isfile", return_value=False)
    @patch("terminal_visual.shutil.which", return_value="/usr/bin/timg")
    def test_skips_when_file_does_not_exist(self, mock_which, mock_isfile, mock_run):
        preview_image_in_terminal("/tmp/nonexistent.png")
        mock_run.assert_not_called()

    @patch("terminal_visual.subprocess.run", side_effect=OSError("spawn failed"))
    @patch("terminal_visual.os.path.isfile", return_value=True)
    @patch("terminal_visual.shutil.which", return_value="/usr/bin/timg")
    def test_silently_handles_subprocess_error(self, mock_which, mock_isfile, mock_run):
        # Should not raise
        preview_image_in_terminal("/tmp/test.png")

    @patch("terminal_visual.subprocess.run")
    @patch("terminal_visual.os.path.isfile", return_value=True)
    @patch("terminal_visual.shutil.which", return_value="/usr/bin/timg")
    def test_passes_correct_geometry(self, mock_which, mock_isfile, mock_run):
        preview_image_in_terminal("/some/image.jpg")
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "timg")
        self.assertEqual(args[1], "-g")
        self.assertEqual(args[2], "80x40")
        self.assertEqual(args[3], "/some/image.jpg")


class TestExtractImagePathFromMarkdown(unittest.TestCase):
    """Tests for extract_image_path_from_markdown()."""

    def test_extracts_local_path(self):
        text = "Here is your image!\n\n![Generated Image](static/generated_images/20250812_test.png)"
        result = extract_image_path_from_markdown(text)
        self.assertEqual(result, "static/generated_images/20250812_test.png")

    def test_ignores_http_urls(self):
        text = "![photo](http://example.com/img.png)"
        result = extract_image_path_from_markdown(text)
        self.assertIsNone(result)

    def test_ignores_https_urls(self):
        text = "![photo](https://cdn.example.com/img.png)"
        result = extract_image_path_from_markdown(text)
        self.assertIsNone(result)

    def test_returns_first_local_path_only(self):
        text = ("![a](static/generated_images/first.png) "
                "![b](static/generated_images/second.png)")
        result = extract_image_path_from_markdown(text)
        self.assertEqual(result, "static/generated_images/first.png")

    def test_returns_none_for_no_images(self):
        text = "Just a plain text reply with no images."
        result = extract_image_path_from_markdown(text)
        self.assertIsNone(result)

    def test_skips_url_returns_local(self):
        text = ("![remote](https://example.com/pic.jpg) "
                "![local](static/uploads/photo.png)")
        result = extract_image_path_from_markdown(text)
        self.assertEqual(result, "static/uploads/photo.png")

    def test_empty_string(self):
        result = extract_image_path_from_markdown("")
        self.assertIsNone(result)

    def test_absolute_local_path(self):
        text = "![img](/home/user/images/test.png)"
        result = extract_image_path_from_markdown(text)
        self.assertEqual(result, "/home/user/images/test.png")


if __name__ == '__main__':
    unittest.main()
