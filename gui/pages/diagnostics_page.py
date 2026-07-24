"""Diagnostics: versions, log tail, last errors."""

from __future__ import annotations

import platform
import sys
from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.paths import log_file_path

if TYPE_CHECKING:
    from gui.app_state import AppState


class DiagnosticsPage(QWidget):
    def __init__(self, state: AppState, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state

        title = QLabel("Diagnostics")
        title.setObjectName("titleLabel")

        self.info = QTextEdit()
        self.info.setReadOnly(True)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        btn = QPushButton("รีเฟรช")
        btn.clicked.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(btn)
        layout.addWidget(QLabel("ระบบ"))
        layout.addWidget(self.info)
        layout.addWidget(QLabel("Log (ท้ายไฟล์)"))
        layout.addWidget(self.log_view, 1)
        self.refresh()

    def refresh(self) -> None:
        lines = [
            f"Python: {sys.version}",
            f"Platform: {platform.platform()}",
            f"Executable: {sys.executable}",
        ]
        try:
            import cv2

            lines.append(f"OpenCV: {cv2.__version__}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"OpenCV: error {exc}")
        try:
            import PySide6

            lines.append(f"PySide6: {PySide6.__version__}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"PySide6: error {exc}")
        try:
            import chess

            lines.append(f"python-chess: {chess.__version__}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"python-chess: error {exc}")
        lines.append(f"Stockfish path: {self.state.engine.path or '(empty)'}")
        lines.append(f"Profile: {self.state.profile.name}")
        lines.append(f"FEN: {self.state.board_state.fen()}")
        lines.append(f"Capture active: {self.state.capture_active}")
        lines.append(f"Auto recalibrate: {self.state.auto_recalibrate}")
        lines.append(f"Templates samples: {self.state.templates.count()}")
        lines.append(f"Confidence threshold: {self.state.profile.thresholds.confidence}")
        lines.append(f"Debounce ms: {self.state.profile.thresholds.debounce_ms}")
        lines.append(f"Overlay enabled: {self.state.overlay._enabled}")
        lines.append("Network upload: disabled (local only)")
        lines.append("Mouse control: disabled (assist only)")
        self.info.setPlainText("\n".join(lines))

        path = log_file_path()
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            self.log_view.setPlainText(text[-12000:])
        else:
            self.log_view.setPlainText("(no log yet)")
