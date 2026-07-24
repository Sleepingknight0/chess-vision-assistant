"""Global app config in user data dir.

API keys are never stored in plaintext. See storage.secret_store.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.paths import config_path, project_root
from storage.secret_store import (
    env_api_key,
    protect_for_storage,
    resolve_api_key,
)


logger = logging.getLogger(__name__)

# Keys that must never be written as plaintext JSON values.
_SECRET_PLAIN_KEYS = frozenset({"grok_api_key"})


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
    # Never persist plaintext. Optional DPAPI blob:
    "grok_api_key_protected": "",
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
    "language": "en",
}


def _sanitize_for_disk(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe to write: drop plaintext secret fields."""
    out = deepcopy(data)
    for key in _SECRET_PLAIN_KEYS:
        out.pop(key, None)
    # Never accidentally keep empty protected field wrong type
    if not isinstance(out.get("grok_api_key_protected", ""), str):
        out["grok_api_key_protected"] = ""
    return out


def sanitize_config_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Public helper for any code that rewrites config.json in-place."""
    return _sanitize_for_disk(data)


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
                    # Example must never inject secrets into live config
                    loaded.pop("grok_api_key", None)
                    loaded.pop("grok_api_key_protected", None)
                    self.data = {**deepcopy(DEFAULT_CONFIG), **loaded}
                except Exception:  # noqa: BLE001
                    pass
            self.save()
            return

        # Migrate legacy plaintext key → DPAPI blob (then strip plaintext on save)
        if self._migrate_legacy_grok_key():
            self.save()

    def _migrate_legacy_grok_key(self) -> bool:
        legacy = str(self.data.get("grok_api_key") or "").strip()
        protected = str(self.data.get("grok_api_key_protected") or "").strip()
        if not legacy:
            # Still strip empty plaintext key if present
            return "grok_api_key" in self.data
        if protected:
            # Prefer existing protected blob; drop plaintext
            self.data.pop("grok_api_key", None)
            return True
        try:
            self.data["grok_api_key_protected"] = protect_for_storage(legacy)
            self.data.pop("grok_api_key", None)
            logger.info("Migrated grok API key to DPAPI-protected storage")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Could not protect API key with DPAPI — key left only in memory until fixed"
            )
            logger.debug("protect error: %s", type(exc).__name__)
            return False

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = _sanitize_for_disk(self.data)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # Keep runtime data free of plaintext too
        for key in _SECRET_PLAIN_KEYS:
            self.data.pop(key, None)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if key in _SECRET_PLAIN_KEYS:
            # Route through secret setter — never store raw
            self.set_grok_api_key(str(value or ""))
            return
        self.data[key] = value

    def get_grok_api_key(self) -> str:
        """Resolved key for runtime use (env > protected > empty)."""
        key, _src = resolve_api_key(
            protected_b64=str(self.data.get("grok_api_key_protected") or ""),
            legacy_plaintext=str(self.data.get("grok_api_key") or ""),
        )
        return key

    def grok_api_key_source(self) -> str:
        _key, src = resolve_api_key(
            protected_b64=str(self.data.get("grok_api_key_protected") or ""),
            legacy_plaintext=str(self.data.get("grok_api_key") or ""),
        )
        return src

    def set_grok_api_key(self, plaintext: str) -> None:
        """Store key as DPAPI blob. Empty clears disk secret.

        If the key currently comes from the environment, an empty UI field
        does not wipe the env — only explicit non-empty values update disk,
        and clearing only clears the protected blob.
        """
        plaintext = (plaintext or "").strip()
        self.data.pop("grok_api_key", None)
        if not plaintext:
            self.data["grok_api_key_protected"] = ""
            return
        # Do not re-persist a key that is identical to env-only secret if user
        # just re-saved settings without changing the field — callers pass the
        # field text; env keys should not be duplicated onto disk.
        if plaintext == env_api_key() and not str(
            self.data.get("grok_api_key_protected") or ""
        ):
            # Keep disk empty; runtime still uses env
            self.data["grok_api_key_protected"] = ""
            return
        try:
            self.data["grok_api_key_protected"] = protect_for_storage(plaintext)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to encrypt API key — refusing to write plaintext to disk"
            )
            logger.debug("encrypt error: %s", type(exc).__name__)
            raise
