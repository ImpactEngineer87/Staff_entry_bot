"""Separate bundled read-only resources from persistent user files."""
from __future__ import annotations

import os
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", SOURCE_ROOT))


def logs_directory(source_root: Path = SOURCE_ROOT) -> Path:
    if not is_frozen():
        return source_root / "logs"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "StaffEntryBot" / "logs"


def practice_launch(source_root: Path = SOURCE_ROOT) -> tuple[list[str], Path, dict[str, str]]:
    environment = os.environ.copy()
    if is_frozen():
        # A separate onefile instance must survive the main window closing.
        environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        return [sys.executable, "--practice"], Path(sys.executable).resolve().parent, environment
    return [sys.executable, str(source_root / "demo_form.py")], source_root, environment
