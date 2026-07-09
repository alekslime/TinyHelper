"""Centralized filesystem paths used across Iris.

All other modules should import paths from here rather than constructing
their own relative paths. This keeps the app portable and makes it easy to
relocate data/log/model directories in the future (e.g. for a Windows
installer that uses %APPDATA%).
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Iris"

# Root of the repository / installed application (folder containing main.py).
ROOT_DIR: Path = Path(__file__).resolve().parent.parent

# --- User data locations -----------------------------------------------
# On Windows this resolves under %APPDATA%\Iris. On other platforms it falls
# back to a local .iris_data folder so development on Linux/macOS still works.
if os.name == "nt":
    _appdata = os.environ.get("APPDATA")
    APP_DATA_DIR: Path = Path(_appdata) / APP_NAME if _appdata else ROOT_DIR / ".iris_data"
else:
    APP_DATA_DIR = ROOT_DIR / ".iris_data"

CONFIG_DIR: Path = APP_DATA_DIR / "config"
LOG_DIR: Path = APP_DATA_DIR / "logs"
DATA_DIR: Path = APP_DATA_DIR / "data"
MODELS_DIR: Path = APP_DATA_DIR / "models"

# Bundled defaults shipped with the repo (read-only, version controlled).
DEFAULT_CONFIG_FILE: Path = ROOT_DIR / "config" / "default_config.yaml"

# Active user config file (created on first run, user-editable, gitignored).
USER_CONFIG_FILE: Path = CONFIG_DIR / "config.yaml"


def ensure_app_directories() -> None:
    """Create all writable application directories if they do not exist yet.

    Safe to call multiple times. Should be called once during application
    startup, before logging or config loading occurs.
    """
    for directory in (APP_DATA_DIR, CONFIG_DIR, LOG_DIR, DATA_DIR, MODELS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
