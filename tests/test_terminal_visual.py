"""Tests for terminal_visual.preview_image_in_terminal()."""

import sys
import os
import unittest
from unittest.mock import patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terminal_visual import preview_image_in_terminal


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


if __name__ == '__main__':
    unittest.main()
