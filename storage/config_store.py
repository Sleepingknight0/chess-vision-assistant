"""Global app config in user data dir."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.paths import config_path, project_root


logger = logging.getLogger(__name__)


DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "active_profile": "roblox_light_dark_cherry",
    "stockfish_path": "",
    "analysis_preset": "balanced",
    "multipv": 3,
    "warped_board_size": 512,
    "confidence_threshold": 0.85,
    "capture_backend": "mss",
    "auto_recalibrate": False,
    "save_move_screenshots": False,
    "grok_api_key": "",
    "grok_model": "grok-4-fast-reasoning",
    "syzygy_path": "",
    "book_path": "",
    "hotkeys": {
        "toggle_capture": "F8",
        "analyze": "F9",
        "toggle_overlay": "F10",
        "undo_detection": "Ctrl+Z",
        "recalibrate": "Ctrl+Shift+C",
    },
    "language": "th",
}


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_path()
        self.data: dict[str, Any] = deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        if self.path.is_file():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                self.data = {**deepcopy(DEFAULT_CONFIG), **loaded}
            except Exception as exc:  # noqa: BLE001
                logger.warning("Config load failed: %s", exc)
        else:
            example = project_root() / "config.example.json"
            if example.is_file():
                try:
                    loaded = json.loads(example.read_text(encoding="utf-8"))
                    self.data = {**deepcopy(DEFAULT_CONFIG), **loaded}
                except Exception:  # noqa: BLE001
                    pass
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
