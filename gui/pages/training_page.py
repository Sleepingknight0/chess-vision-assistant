"""Template training / labeling page (Phase 3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.widgets.board_view import BoardView
from gui.widgets.capture_preview import CapturePreview
from vision.grid import BoardGrid
from vision.templates import PIECE_KEYS, TemplateLibrary

if TYPE_CHECKING:
    from gui.app_state import AppState


class TrainingPage(QWidget):
    def __init__(self, state: AppState, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state
        self.library = TemplateLibrary()

        title = QLabel("Template Training")
        title.setObjectName("titleLabel")
        hint = QLabel(
            "คลิกช่องบนกระดาน 2D แล้วระบุชนิดหมากเพื่อเก็บตัวอย่างภาพ "
            "(ใช้ตอน Recovery / ตำแหน่งไม่มาตรฐาน — ไม่รับประกันความแม่นยำบนโมเดล 3D)"
        )
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)

        self.preview = CapturePreview()
        self.board_view = BoardView()
        self.board_view.set_board(state.board_state.board)
        self.board_view.square_clicked.connect(self._on_square)

        self.piece_combo = QComboBox()
        labels = {
            "P": "Pawn White",
            "N": "Knight White",
            "B": "Bishop White",
            "R": "Rook White",
            "Q": "Queen White",
            "K": "King White",
            "p": "Pawn Black",
            "n": "Knight Black",
            "b": "Bishop Black",
            "r": "Rook Black",
            "q": "Queen Black",
            "k": "King Black",
        }
        for k in PIECE_KEYS:
            self.piece_combo.addItem(f"{labels[k]} ({k})", k)

        self.lbl_counts = QLabel()
        self._refresh_counts()

        btn_save = QPushButton("บันทึกตัวอย่างช่องที่เลือก")
        btn_save.setObjectName("primaryButton")
        btn_save.clicked.connect(self._save_selected)
        self._selected_sq: Optional[str] = None

        btn_reload = QPushButton("โหลด Template ใหม่")
        btn_reload.clicked.connect(self._reload)

        row = QHBoxLayout()
        row.addWidget(QLabel("ชนิดหมาก:"))
        row.addWidget(self.piece_combo, 1)
        row.addWidget(btn_save)
        row.addWidget(btn_reload)

        body = QHBoxLayout()
        body.addWidget(self.preview, 1)
        body.addWidget(self.board_view, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(row)
        layout.addWidget(self.lbl_counts)
        layout.addLayout(body, 1)

        state.capture_changed.connect(self._on_capture)
        state.board_changed.connect(lambda: self.board_view.set_board(state.board_state.board))

    def _refresh_counts(self) -> None:
        parts = [f"{k}:{self.library.count(k)}" for k in PIECE_KEYS]
        self.lbl_counts.setText("ตัวอย่าง: " + " ".join(parts))

    def _on_capture(self) -> None:
        if self.state.last_warped_bgr is not None:
            grid = BoardGrid(
                size=self.state.last_warped_bgr.shape[0],
                orientation=self.state.orientation,
            )
            self.preview.set_grid(grid)
            self.preview.set_image(self.state.last_warped_bgr)

    def _on_square(self, sq: str) -> None:
        self._selected_sq = sq
        self.state.status_message.emit(f"เลือกช่อง {sq} สำหรับเก็บ template")

    def _save_selected(self) -> None:
        if not self._selected_sq:
            QMessageBox.information(self, "ยังไม่เลือกช่อง", "คลิกช่องบนกระดาน 2D ก่อน")
            return
        if self.state.last_warped_bgr is None:
            QMessageBox.warning(self, "ไม่มีภาพ", "จับภาพกระดานก่อน")
            return
        grid = BoardGrid(
            size=self.state.last_warped_bgr.shape[0],
            orientation=self.state.orientation,
        )
        crop = grid.crop_cell(self.state.last_warped_bgr, self._selected_sq, 0.75)
        symbol = self.piece_combo.currentData()
        self.library.add_sample(symbol, crop)
        self._refresh_counts()
        self.state.status_message.emit(f"บันทึก template {symbol} จากช่อง {self._selected_sq}")

    def _reload(self) -> None:
        self.library.load()
        self._refresh_counts()
