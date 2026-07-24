"""2D chess board widget with arrows for recommended moves."""

from __future__ import annotations

from typing import Optional

import chess
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPolygonF
from PySide6.QtWidgets import QWidget

from board_detection.orientation import BoardOrientation


# Outline glyphs for white, filled for black (readable on most Windows fonts).
PIECE_UNICODE = {
    "P": "♙",
    "N": "♘",
    "B": "♗",
    "R": "♖",
    "Q": "♕",
    "K": "♔",
    "p": "♟",
    "n": "♞",
    "b": "♝",
    "r": "♜",
    "q": "♛",
    "k": "♚",
}

ARROW_COLORS = [
    QColor(46, 204, 113, 200),   # best green
    QColor(52, 152, 219, 180),   # 2nd blue
    QColor(241, 196, 15, 160),   # 3rd yellow
    QColor(155, 89, 182, 150),
    QColor(230, 126, 34, 140),
]


class BoardView(QWidget):
    square_clicked = Signal(str)  # algebraic

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._board = chess.Board()
        self._orientation = BoardOrientation()
        self._arrows: list[tuple[str, str, int]] = []  # from, to, rank
        self._selected: Optional[str] = None
        self._highlight_from: Optional[str] = None
        self._highlight_to: Optional[str] = None
        self.setMinimumSize(320, 320)
        self.setMouseTracking(True)

    def set_board(self, board: chess.Board) -> None:
        self._board = board.copy(stack=False)
        self.update()

    def set_fen(self, fen: str) -> None:
        try:
            self._board = chess.Board(fen)
            self.update()
        except ValueError:
            pass

    def set_orientation(self, orientation: BoardOrientation) -> None:
        self._orientation = orientation
        self.update()

    def set_arrows(self, arrows: list[tuple[str, str, int]]) -> None:
        self._arrows = list(arrows)
        if arrows:
            self._highlight_from = arrows[0][0]
            self._highlight_to = arrows[0][1]
        else:
            self._highlight_from = None
            self._highlight_to = None
        self.update()

    def clear_arrows(self) -> None:
        self._arrows.clear()
        self._highlight_from = None
        self._highlight_to = None
        self.update()

    def _square_size(self) -> float:
        return min(self.width(), self.height()) / 8.0

    def _origin(self) -> tuple[float, float]:
        s = self._square_size() * 8
        return (self.width() - s) / 2, (self.height() - s) / 2

    def _square_rect(self, square: str) -> QRectF:
        col, row = self._orientation.square_to_display(square)
        ox, oy = self._origin()
        s = self._square_size()
        return QRectF(ox + col * s, oy + row * s, s, s)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        light = QColor(240, 217, 181)
        dark = QColor(181, 136, 99)
        ox, oy = self._origin()
        s = self._square_size()

        for row in range(8):
            for col in range(8):
                sq = self._orientation.display_to_square(col, row)
                rect = QRectF(ox + col * s, oy + row * s, s, s)
                is_light = (col + row) % 2 == 0
                color = light if is_light else dark
                if sq == self._highlight_from:
                    color = QColor(241, 196, 15, 220)
                elif sq == self._highlight_to:
                    color = QColor(46, 204, 113, 200)
                elif sq == self._selected:
                    color = QColor(108, 92, 231, 180)
                painter.fillRect(rect, color)

                piece = self._board.piece_at(chess.parse_square(sq))
                if piece:
                    symbol = PIECE_UNICODE.get(piece.symbol(), piece.symbol())
                    font = QFont("Segoe UI Symbol", int(s * 0.55))
                    painter.setFont(font)
                    # White pieces: dark outline look; Black pieces: solid dark
                    if piece.color == chess.WHITE:
                        painter.setPen(QColor(25, 25, 30))
                    else:
                        painter.setPen(QColor(15, 15, 18))
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, symbol)

                # coordinate labels on edges
                if col == 0:
                    painter.setPen(QColor(70, 55, 40))
                    painter.setFont(QFont("Segoe UI", max(8, int(s * 0.16))))
                    painter.drawText(
                        rect.adjusted(2, 2, 0, 0),
                        Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                        sq[1],
                    )
                if row == 7:
                    painter.setPen(QColor(70, 55, 40))
                    painter.setFont(QFont("Segoe UI", max(8, int(s * 0.16))))
                    painter.drawText(
                        rect.adjusted(0, 0, -2, -2),
                        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
                        sq[0],
                    )

        for fr, to, rank in self._arrows:
            color = ARROW_COLORS[min(rank, len(ARROW_COLORS) - 1)]
            self._draw_arrow(painter, fr, to, color)

        painter.end()

    def _draw_arrow(self, painter: QPainter, fr: str, to: str, color: QColor) -> None:
        r1 = self._square_rect(fr)
        r2 = self._square_rect(to)
        p1 = r1.center()
        p2 = r2.center()
        pen = QPen(color, max(3.0, self._square_size() * 0.12), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(QBrush(color))
        painter.drawLine(p1, p2)
        # arrow head
        import math

        angle = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
        head = self._square_size() * 0.28
        a1 = angle + math.pi * 0.85
        a2 = angle - math.pi * 0.85
        pts = QPolygonF(
            [
                p2,
                QPointF(p2.x() + head * math.cos(a1), p2.y() + head * math.sin(a1)),
                QPointF(p2.x() + head * math.cos(a2), p2.y() + head * math.sin(a2)),
            ]
        )
        painter.drawPolygon(pts)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        ox, oy = self._origin()
        s = self._square_size()
        x = event.position().x() - ox
        y = event.position().y() - oy
        if x < 0 or y < 0 or x >= s * 8 or y >= s * 8:
            return
        col = int(x // s)
        row = int(y // s)
        sq = self._orientation.display_to_square(col, row)
        self._selected = sq
        self.square_clicked.emit(sq)
        self.update()
