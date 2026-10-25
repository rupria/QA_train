"""Operating-system paths for user-owned QA Train runtime data."""

from __future__ import annotations

import os
from pathlib import Path
import sys


APP_DATA_ENV = "QA_TRAIN_DATA_DIR"


def app_data_root() -> Path:
    """Return a local data directory without creating it."""
    override = os.environ.get(APP_DATA_ENV)
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "QA Train"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "QA Train"
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "qa-train"
