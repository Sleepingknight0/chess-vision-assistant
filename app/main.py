"""Chess God Board entry point — side-panel Stockfish coach."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.logging_setup import setup_logging
from app.paths import styles_path
from gui.god_board import GodBoardWindow
from gui.theme import apply_dark_theme

logger = logging.getLogger(__name__)


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    setup_logging()
    logger.info("Starting Chess God Board")

    app = QApplication(sys.argv)
    app.setApplicationName("Chess God Board")
    app.setOrganizationName("ChessVisionAssistant")
    apply_dark_theme(app, styles_path())

    window = GodBoardWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
