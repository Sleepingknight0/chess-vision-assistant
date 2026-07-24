"""User-data and project path helpers. Settings never write into Program Files."""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "ChessVisionAssistant"


def project_root() -> Path:
    """Repository / install root (where assets and package live)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    return project_root() / "assets"


def styles_path() -> Path:
    return assets_dir() / "styles" / "dark.qss"


def user_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def profiles_dir() -> Path:
    path = user_data_dir() / "profiles"
    path.mkdir(parents=True, exist_ok=True)
    return path


def templates_dir() -> Path:
    path = user_data_dir() / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = user_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def exports_dir() -> Path:
    path = user_data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return user_data_dir() / "config.json"


def log_file_path() -> Path:
    return logs_dir() / "app.log"
