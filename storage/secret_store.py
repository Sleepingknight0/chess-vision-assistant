"""Protect secrets at rest (Windows DPAPI) and resolve from environment.

Priority when reading an API key:
  1. Environment variables (never written to disk by this module)
  2. DPAPI-protected blob in config (`*_protected`)
  3. Legacy plaintext config field (migrated away on next save)

Never log or return secrets into diagnostics/export paths.
"""

from __future__ import annotations

import base64
import ctypes
import logging
import os
import re
import sys
from ctypes import wintypes
from typing import Iterable

logger = logging.getLogger(__name__)

# Common env names for xAI / Grok (and generic aliases).
GROK_ENV_NAMES: tuple[str, ...] = (
    "XAI_API_KEY",
    "GROK_API_KEY",
    "CHESS_VISION_XAI_API_KEY",
)


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob_from_bytes(data: bytes) -> DATA_BLOB:
    blob = DATA_BLOB()
    blob.cbData = len(data)
    blob.pbData = ctypes.cast(
        ctypes.create_string_buffer(data, len(data)),
        ctypes.POINTER(ctypes.c_char),
    )
    return blob


def _bytes_from_blob(blob: DATA_BLOB) -> bytes:
    return ctypes.string_at(blob.pbData, blob.cbData)


def dpapi_protect(plaintext: str) -> str:
    """Encrypt with current-user DPAPI → base64 (Windows only)."""
    if not plaintext:
        return ""
    if sys.platform != "win32":
        raise OSError("DPAPI is only available on Windows")
    data = plaintext.encode("utf-8")
    in_blob = _blob_from_bytes(data)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "ChessVisionAssistant",
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError(f"CryptProtectData failed (err={ctypes.GetLastError()})")
    try:
        return base64.b64encode(_bytes_from_blob(out_blob)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def dpapi_unprotect(token_b64: str) -> str:
    """Decrypt base64 DPAPI blob (Windows only)."""
    if not token_b64:
        return ""
    if sys.platform != "win32":
        raise OSError("DPAPI is only available on Windows")
    raw = base64.b64decode(token_b64.encode("ascii"))
    in_blob = _blob_from_bytes(raw)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError(f"CryptUnprotectData failed (err={ctypes.GetLastError()})")
    try:
        return _bytes_from_blob(out_blob).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def env_api_key(names: Iterable[str] = GROK_ENV_NAMES) -> str:
    for name in names:
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return ""


def resolve_api_key(
    *,
    protected_b64: str = "",
    legacy_plaintext: str = "",
    env_names: Iterable[str] = GROK_ENV_NAMES,
) -> tuple[str, str]:
    """Return (key, source) where source is env|protected|legacy|empty."""
    env = env_api_key(env_names)
    if env:
        return env, "env"
    if protected_b64:
        try:
            key = dpapi_unprotect(protected_b64).strip()
            if key:
                return key, "protected"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to decrypt protected API key (will ignore blob)")
            logger.debug("decrypt error detail: %s", type(exc).__name__)
    legacy = (legacy_plaintext or "").strip()
    if legacy:
        return legacy, "legacy"
    return "", "empty"


def protect_for_storage(plaintext: str) -> str:
    """Return DPAPI blob for disk; empty input → empty string."""
    plaintext = (plaintext or "").strip()
    if not plaintext:
        return ""
    return dpapi_protect(plaintext)


def mask_secret(value: str, *, keep: int = 4) -> str:
    """Safe display form: xai-****abcd or (empty)."""
    value = (value or "").strip()
    if not value:
        return "(empty)"
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}…{value[-keep:]}"


def redact_text(text: str) -> str:
    """Strip bearer tokens / key-shaped strings from log/diagnostic text."""
    if not text:
        return text
    out = text
    out = re.sub(r"(?i)Bearer\s+[A-Za-z0-9_\-.=+/]{8,}", "Bearer ***REDACTED***", out)
    out = re.sub(r"(?i)\bxai-[A-Za-z0-9]{8,}", "xai-***REDACTED***", out)
    out = re.sub(r"(?i)\bsk-[A-Za-z0-9]{8,}", "sk-***REDACTED***", out)
    out = re.sub(
        r"(?i)(api[_-]?key\s*[\"']?\s*[:=]\s*[\"']?)([A-Za-z0-9_\-.=+/]{8,})",
        r"\1***REDACTED***",
        out,
    )
    out = re.sub(
        r"(?i)(Authorization\s*[\"']?\s*[:=]\s*[\"']?)([^\s\"']{8,})",
        r"\1***REDACTED***",
        out,
    )
    return out


class RedactingFilter(logging.Filter):
    """Logging filter that redacts API-key-shaped substrings."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact_text(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: redact_text(v) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        redact_text(a) if isinstance(a, str) else a for a in record.args
                    )
        except Exception:  # noqa: BLE001
            pass
        return True


def key_is_from_environment(env_names: Iterable[str] = GROK_ENV_NAMES) -> bool:
    return bool(env_api_key(env_names))
