"""FEN text field with validate/apply."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from chess_core.fen_utils import is_valid_fen, normalize_fen


class FenEditor(QWidget):
    fen_applied = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Paste FEN here…")
        self.status = QLabel("")
        self.status.setObjectName("mutedLabel")
        btn = QPushButton("Apply FEN")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self.apply)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("FEN:"))
        layout.addWidget(self.edit, 1)
        layout.addWidget(btn)
        layout.addWidget(self.status)

    def set_fen(self, fen: str) -> None:
        self.edit.setText(fen)

    def apply(self) -> None:
        text = self.edit.text().strip()
        if not is_valid_fen(text):
            self.status.setObjectName("statusError")
            self.status.setText("Invalid FEN")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            return
        fen = normalize_fen(text)
        self.edit.setText(fen)
        self.status.setObjectName("statusOk")
        self.status.setText("OK")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.fen_applied.emit(fen)
