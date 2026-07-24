"""Move history, PGN export, and post-game review."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.paths import exports_dir
from storage.pgn_export import pgn_from_uci_list, review_game

if TYPE_CHECKING:
    from gui.app_state import AppState


class HistoryPage(QWidget):
    def __init__(self, state: AppState, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state

        title = QLabel("Move History & Review")
        title.setObjectName("titleLabel")

        self.list = QListWidget()
        self.fen_box = QTextEdit()
        self.fen_box.setReadOnly(True)
        self.fen_box.setMaximumHeight(70)
        self.review_box = QTextEdit()
        self.review_box.setReadOnly(True)
        self.review_box.setPlaceholderText("ผล Review หลังจบเกมจะแสดงที่นี่…")

        self.chk_shots = QCheckBox("บันทึก Screenshot กระดานแต่ละตา (เก็บในเครื่องเท่านั้น)")
        self.chk_shots.setChecked(state.save_move_screenshots)
        self.chk_shots.toggled.connect(self._toggle_shots)

        btn_refresh = QPushButton("รีเฟรช")
        btn_refresh.clicked.connect(self.refresh)
        btn_copy_fen = QPushButton("Copy FEN")
        btn_copy_fen.clicked.connect(self.copy_fen)
        btn_undo = QPushButton("Undo ล่าสุด")
        btn_undo.clicked.connect(self.undo)
        btn_pgn = QPushButton("Export PGN")
        btn_pgn.setObjectName("primaryButton")
        btn_pgn.clicked.connect(self.export_pgn)
        btn_review = QPushButton("Review เกม (Blunder/Mistake)")
        btn_review.clicked.connect(self.run_review)

        row = QHBoxLayout()
        for b in (btn_refresh, btn_copy_fen, btn_undo, btn_pgn, btn_review):
            row.addWidget(b)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.chk_shots)
        layout.addLayout(row)
        layout.addWidget(QLabel("SAN / UCI"))
        layout.addWidget(self.list, 1)
        layout.addWidget(QLabel("FEN ปัจจุบัน"))
        layout.addWidget(self.fen_box)
        layout.addWidget(QLabel("Review"))
        layout.addWidget(self.review_box, 1)
        self.refresh()
        state.board_changed.connect(self.refresh)

    def _toggle_shots(self, on: bool) -> None:
        self.state.save_move_screenshots = on
        self.state.config.set("save_move_screenshots", on)
        self.state.config.save()

    def refresh(self) -> None:
        self.list.clear()
        sans = self.state.board_state.san_history()
        ucis = self.state.board_state.history_uci
        for i, uci in enumerate(ucis):
            san = sans[i] if i < len(sans) else uci
            self.list.addItem(f"{i + 1}. {san}  [{uci}]")
        self.fen_box.setPlainText(self.state.board_state.fen())

    def copy_fen(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.state.board_state.fen())
        self.state.status_message.emit("คัดลอก FEN แล้ว")

    def undo(self) -> None:
        if self.state.board_state.undo_last():
            self.state.detection.reset(self.state.board_state.board)
            self.state.board_changed.emit()
            self.state.status_message.emit("ย้อนแล้ว")

    def export_pgn(self) -> None:
        pgn = pgn_from_uci_list(
            self.state.board_state.history_uci,
            white=self.state.team.white_label,
            black=self.state.team.black_label,
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "บันทึก PGN",
            str(exports_dir() / "game.pgn"),
            "PGN (*.pgn)",
        )
        if not path:
            return
        Path(path).write_text(pgn, encoding="utf-8")
        self.state.status_message.emit(f"Export PGN → {path}")
        QMessageBox.information(self, "Export แล้ว", f"บันทึกที่\n{path}")

    def run_review(self) -> None:
        ucis = self.state.board_state.history_uci
        if not ucis:
            QMessageBox.information(self, "ว่าง", "ยังไม่มีการเดิน")
            return
        ok, msg = self.state.engine.validate()
        if not ok:
            QMessageBox.warning(self, "Stockfish", msg)
            return
        self.review_box.setPlainText("กำลัง Review… (local เท่านั้น)")
        try:
            reviews = review_game(
                self.state.engine,
                ucis,
                movetime_ms=150,
            )
            lines = []
            for r in reviews:
                loss = f"{r.loss_cp:.0f}cp" if r.loss_cp is not None else "—"
                lines.append(
                    f"{r.ply}. {r.san} [{r.uci}]  {r.classification.upper()}  "
                    f"loss={loss}  best={r.best_move_san or '—'}"
                )
            self.review_box.setPlainText("\n".join(lines) if lines else "ไม่มีผล")
            self.state.status_message.emit("Review เสร็จ")
        except Exception as exc:  # noqa: BLE001
            self.review_box.setPlainText(str(exc))
            QMessageBox.warning(self, "Review ล้มเหลว", str(exc))
