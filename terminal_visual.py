# [FILE: terminal_visual.py]
# [VERSION: 1.0.0]
# [DATE: 2026-02-15]
# [PROJECT: HKKM - Yuzu Companion]
# [DESCRIPTION: Terminal image preview utility using timg]
# [AUTHOR: Project Lead: Bani Baskara]
# [TEAM: Deepseek, GPT, Qwen, Gemini, Aihara]
# [REPOSITORY: https://guthib.com/icedeyes12]
# [LICENSE: MIT]

import os
import re
import shutil
import subprocess
from typing import Optional


def extract_image_path_from_markdown(text: str) -> Optional[str]:
    """Return the first local image path found in markdown ``![...](path)`` syntax.

    Only paths that do **not** start with ``http://`` or ``https://`` are
    considered local.  Returns ``None`` when no local path is found.
    """
    for match in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)', text):
        path = match.group(1)
        if not path.startswith(("http://", "https://")):
            return path
    return None


def preview_image_in_terminal(image_path: str) -> None:
    """Display an image in the terminal using timg.

    Silently does nothing when timg is not installed or when
    *image_path* does not point to an existing file.
    """
    if not shutil.which("timg"):
        return

    if not os.path.isfile(image_path):
        return

    try:
        subprocess.run(["timg", "-g", "80x40", image_path])
    except Exception:
        pass
