"""resource_path(): THE way to reach bundled data files (CLAUDE.md:
PYINSTALLER RESOURCES). Dev runs resolve relative to this repo; frozen
runs resolve inside the PyInstaller onefile extraction dir
(sys._MEIPASS). Never open bundled files by relative path — cwd is the
exe's folder when frozen, which is NOT where bundled data lives.

Every file bundled this way must also appear in the spec's `datas`
(currently: ui/assets/*)."""

from __future__ import annotations

import os
import sys


def resource_path(relative: str) -> str:
    base = getattr(sys, '_MEIPASS', None) or os.path.dirname(
        os.path.abspath(__file__))
    return os.path.join(base, relative)
