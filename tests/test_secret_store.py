"""Security: API keys must not leak to disk or logs as plaintext."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import pytest

from storage.config_store import ConfigStore, sanitize_config_dict
from storage.secret_store import (
    RedactingFilter,
    dpapi_protect,
    dpapi_unprotect,
    redact_text,
    resolve_api_key,
)


def test_redact_bearer_and_xai_keys() -> None:
    raw = "Authorization: Bearer xai-supersecretkey12345 and also sk-abcdefghi123456"
    out = redact_text(raw)
    assert "supersecret" not in out
    assert "abcdefghi" not in out
    assert "REDACTED" in out
    assert "Bearer" in out


def test_redact_filter_on_log_record() -> None:
    filt = RedactingFilter()
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="got key xai-ABCDEFGHijklmnop",
        args=(),
        exc_info=None,
    )
    assert filt.filter(record) is True
    assert "ABCDEFGH" not in record.msg
    assert "REDACTED" in record.msg


def test_sanitize_strips_plaintext_key() -> None:
    data = {
        "stockfish_path": "C:/sf.exe",
        "grok_api_key": "xai-should-not-be-written",
        "grok_api_key_protected": "blob",
    }
    clean = sanitize_config_dict(data)
    assert "grok_api_key" not in clean
    assert clean["grok_api_key_protected"] == "blob"
    assert clean["stockfish_path"] == "C:/sf.exe"


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_dpapi_roundtrip() -> None:
    secret = "xai-test-roundtrip-key-not-real"
    blob = dpapi_protect(secret)
    assert secret not in blob
    assert dpapi_unprotect(blob) == secret


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_config_store_never_writes_plaintext(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Isolate from real env keys
    for name in ("XAI_API_KEY", "GROK_API_KEY", "CHESS_VISION_XAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    path = tmp_path / "config.json"
    store = ConfigStore(path=path)
    store.set_grok_api_key("xai-plaintext-must-not-appear-on-disk")
    store.save()

    raw = path.read_text(encoding="utf-8")
    assert "xai-plaintext-must-not-appear-on-disk" not in raw
    assert "grok_api_key_protected" in raw
    disk = json.loads(raw)
    assert "grok_api_key" not in disk
    assert disk["grok_api_key_protected"]

    # Reload resolves key
    store2 = ConfigStore(path=path)
    assert store2.get_grok_api_key() == "xai-plaintext-must-not-appear-on-disk"
    assert store2.grok_api_key_source() == "protected"


def test_env_key_wins_over_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY", "xai-from-environment-only")
    path = tmp_path / "config.json"
    store = ConfigStore(path=path)
    # Even if protected empty, env wins
    assert store.get_grok_api_key() == "xai-from-environment-only"
    assert store.grok_api_key_source() == "env"


def test_legacy_plaintext_migrates_on_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform != "win32":
        pytest.skip("DPAPI is Windows-only")
    for name in ("XAI_API_KEY", "GROK_API_KEY", "CHESS_VISION_XAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"version": 1, "grok_api_key": "xai-legacy-plain-key-value"}),
        encoding="utf-8",
    )
    store = ConfigStore(path=path)
    disk = json.loads(path.read_text(encoding="utf-8"))
    assert "grok_api_key" not in disk
    assert disk.get("grok_api_key_protected")
    assert store.get_grok_api_key() == "xai-legacy-plain-key-value"


def test_resolve_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY", "env-key")
    key, src = resolve_api_key(protected_b64="", legacy_plaintext="legacy")
    assert key == "env-key" and src == "env"
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("CHESS_VISION_XAI_API_KEY", raising=False)
    key, src = resolve_api_key(protected_b64="", legacy_plaintext="legacy-only")
    assert key == "legacy-only" and src == "legacy"
