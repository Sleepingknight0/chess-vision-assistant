"""Application logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.paths import log_file_path
from storage.secret_store import RedactingFilter


def setup_logging(level: int = logging.INFO) -> None:
    log_path = log_file_path()
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    redact = RedactingFilter()

    file_handler = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)
    file_handler.addFilter(redact)
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(level)
    console.addFilter(redact)
    root.addHandler(console)

    # Also filter any third-party / late handlers on the root logger
    root.addFilter(redact)

    logging.getLogger(__name__).info("Logging initialized → %s", log_path)
