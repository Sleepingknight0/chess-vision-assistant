"""Click-to-place piece editor."""

from __future__ import annotations

from typing import Optional

import chess
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.widgets.board_view import BoardView


PIECE_CHOICES = [
    ("ลบหมาก", None),
    ("♙ Pawn White", "P"),
    ("♘ Knight White", "N"),
    ("♗ Bishop White", "B"),
    ("♖ Rook White", "R"),
    ("♕ Queen White", "Q"),
    ("♔ King White", "K"),
    ("♟ Pawn Black", "p"),
    ("♞ Knight Black", "n"),
    ("♝ Bishop Black", "b"),
    ("♜ Rook Black", "r"),
    ("♛ Queen Black", "q"),
    ("♚ King Black", "k"),
]


class PositionEditorWidget(QWidget):
    position_changed = Signal(str)  # fen

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.board = chess.Board()
        self.board_view = BoardView()
        self.board_view.set_board(self.board)
        self.board_view.square_clicked.connect(self._on_square)

        self.piece_combo = QComboBox()
        for label, _ in PIECE_CHOICES:
            self.piece_combo.addItem(label)

        self.turn_combo = QComboBox()
        self.turn_combo.addItems(["ตา White (Light Cherry)", "ตา Black (Dark Cherry)"])
        self.turn_combo.currentIndexChanged.connect(self._on_turn)

        btn_standard = QPushButton("ตำแหน่งมาตรฐาน")
        btn_standard.clicked.connect(self.load_standard)
        btn_clear = QPushButton("ล้างกระดาน")
        btn_clear.clicked.connect(self.clear_board)
        btn_copy = QPushButton("Copy FEN")
        btn_copy.clicked.connect(self.copy_fen)

        tools = QHBoxLayout()
        tools.addWidget(QLabel("วางหมาก:"))
        tools.addWidget(self.piece_combo, 1)

        tools2 = QHBoxLayout()
        tools2.addWidget(QLabel("ตาเดิน:"))
        tools2.addWidget(self.turn_combo, 1)
        tools2.addWidget(btn_standard)
        tools2.addWidget(btn_clear)
        tools2.addWidget(btn_copy)

        layout = QVBoxLayout(self)
        layout.addLayout(tools)
        layout.addLayout(tools2)
        layout.addWidget(self.board_view, 1)
        tip = QLabel("คลิกช่อง = วางหมากที่เลือก · เลือกลบหมากแล้วคลิก = ลบ")
        tip.setStyleSheet("color:#9aa0a6;")
        tip.setWordWrap(True)
        layout.addWidget(tip)

    def set_fen(self, fen: str) -> None:
        try:
            self.board = chess.Board(fen)
            self.board_view.set_board(self.board)
            self.turn_combo.blockSignals(True)
            self.turn_combo.setCurrentIndex(0 if self.board.turn == chess.WHITE else 1)
            self.turn_combo.blockSignals(False)
            self._emit_fen()
        except ValueError:
            pass

    def load_standard(self) -> None:
        self.board.reset()
        self.board_view.set_board(self.board)
        self.turn_combo.setCurrentIndex(0)
        self._emit_fen()

    def clear_board(self) -> None:
        self.board.clear()
        self.board.set_castling_fen("-")
        self.board.turn = chess.WHITE
        self.board_view.set_board(self.board)
        self._emit_fen()

    def _on_turn(self, idx: int) -> None:
        self.board.turn = chess.WHITE if idx == 0 else chess.BLACK
        self.board_view.set_board(self.board)
        self._emit_fen()

    def _on_square(self, square: str) -> None:
        symbol = PIECE_CHOICES[self.piece_combo.currentIndex()][1]
        sq = chess.parse_square(square)
        if symbol is None:
            self.board.remove_piece_at(sq)
        else:
            self.board.set_piece_at(sq, chess.Piece.from_symbol(symbol))
        self.board_view.set_board(self.board)
        self._emit_fen()

    def _emit_fen(self) -> None:
        self.position_changed.emit(self.board.fen())

    def copy_fen(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.board.fen())
        self._emit_fen()

    def fen(self) -> str:
        return self.board.fen()
