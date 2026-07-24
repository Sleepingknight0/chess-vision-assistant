"""Theme application helpers."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


logger = logging.getLogger(__name__)


def apply_dark_theme(app: QApplication, qss_path: Path | None = None) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(18, 20, 26))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(232, 234, 237))
    palette.setColor(QPalette.ColorRole.Base, QColor(26, 29, 38))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(37, 42, 54))
    palette.setColor(QPalette.ColorRole.Text, QColor(232, 234, 237))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 51, 64))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(232, 234, 237))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(108, 92, 231))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(37, 42, 54))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(232, 234, 237))
    app.setPalette(palette)

    if qss_path and qss_path.is_file():
        try:
            app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load QSS: %s", exc)
