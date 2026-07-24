"""Transparent always-on-top click-through overlay for move arrows."""

from __future__ import annotations

import logging
import sys
from typing import Optional

import chess
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from capture.base import CaptureRegion
from vision.grid import BoardGrid
from vision.perspective import PerspectiveCalibration

logger = logging.getLogger(__name__)

ARROW_COLORS = [
    QColor(46, 204, 113, 220),
    QColor(52, 152, 219, 200),
    QColor(241, 196, 15, 190),
    QColor(155, 89, 182, 180),
    QColor(230, 126, 34, 170),
]

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


class OverlayWindow(QWidget):
    """Transparent overlay drawn only over the board ROI; click-through.

    Never blocks the main app or game input when working correctly.
    Optional interactive mode: clicks on board squares are emitted as
    `square_clicked` (and then the window is NOT click-through).
    """

    square_clicked = Signal(str)  # algebraic square, only in interactive mode

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Chess Vision Overlay")
        # NOTE: deliberately NOT using Qt.WindowType.WindowTransparentForInput.
        # That flag can't be toggled reliably at runtime (setWindowFlags won't
        # drop it), which permanently blocked clicks in interactive mode.
        # Click-through is instead controlled by WS_EX_TRANSPARENT (Win32) plus
        # WA_TransparentForMouseEvents, both toggled in _apply_clickthrough().
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._arrows: list[tuple[str, str, int]] = []
        self._label = ""
        self._eval = ""
        self._region: Optional[CaptureRegion] = None
        self._calibration: Optional[PerspectiveCalibration] = None
        self._grid: Optional[BoardGrid] = None
        self._opacity = 0.85
        self._thickness = 4
        self._enabled = False
        self._interactive = False
        self._position: Optional[chess.Board] = None  # ghost pieces
        self._selected: Optional[str] = None
        self._ghost_opacity = 0.25
        self._show_grid = True
        self.resize(1, 1)
        self.hide()

    def set_board_geometry(
        self,
        region: CaptureRegion,
        calibration: PerspectiveCalibration,
        grid: BoardGrid,
    ) -> None:
        self._region = region
        self._calibration = calibration
        self._grid = grid
        self._reapply_geometry()
        self._apply_clickthrough()
        self.update()

    def _reapply_geometry(self) -> None:
        if self._region is None:
            return
        # Size to board ROI only (+ padding), not the entire virtual desktop
        pad = 40
        r = self._region
        self.setGeometry(
            QRect(
                int(r.left - pad),
                int(r.top - pad),
                int(r.width + pad * 2),
                int(r.height + pad * 2 + 36),
            )
        )

    def set_style(self, opacity: float = 0.85, thickness: int = 4) -> None:
        self._opacity = max(0.2, min(1.0, opacity))
        self._thickness = max(1, min(12, thickness))
        self.update()

    def set_arrows(
        self,
        arrows: list[tuple[str, str, int]],
        label: str = "",
        evaluation: str = "",
    ) -> None:
        self._arrows = list(arrows)
        self._label = label
        self._eval = evaluation
        if self._enabled:
            self.update()

    def clear(self) -> None:
        self._arrows.clear()
        self._label = ""
        self._eval = ""
        if self._enabled:
            self.update()

    def set_position(self, board: Optional[chess.Board]) -> None:
        """Board to render as translucent ghost pieces over the real game."""
        self._position = board.copy(stack=False) if board is not None else None
        if self._enabled:
            self.update()

    def set_ghost_opacity(self, opacity: float) -> None:
        self._ghost_opacity = max(0.0, min(0.6, opacity))
        if self._enabled:
            self.update()

    def set_show_grid(self, show: bool) -> None:
        self._show_grid = bool(show)
        if self._enabled:
            self.update()

    def set_selected(self, square: Optional[str]) -> None:
        self._selected = square
        if self._enabled:
            self.update()

    def set_interactive(self, interactive: bool) -> None:
        """Interactive: clicks land on the overlay and map to board squares.

        While on, clicks do NOT pass through to the game underneath. This is
        driven by WS_EX_TRANSPARENT + WA_TransparentForMouseEvents (both handled
        in _apply_clickthrough), NOT a window flag — those can't be toggled
        reliably once the window exists.
        """
        self._interactive = bool(interactive)
        if not self._interactive:
            self._selected = None
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, not self._interactive
        )
        self._apply_clickthrough()
        if self._enabled:
            self.update()

    def square_at_local(self, pos: QPointF) -> Optional[str]:
        """Map a widget-local point to an algebraic square (None if outside)."""
        if not self._region or not self._calibration or not self._grid:
            return None
        geo = self.geometry()
        ix = pos.x() + geo.x() - self._region.left
        iy = pos.y() + geo.y() - self._region.top
        try:
            bx, by = self._calibration.image_to_board_xy(ix, iy)
        except Exception:  # noqa: BLE001
            return None
        size = float(self._calibration.warped_size)
        if not (0 <= bx < size and 0 <= by < size):
            return None
        return self._grid.square_at_pixel(bx, by)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self._interactive or event.button() != Qt.MouseButton.LeftButton:
            return
        sq = self.square_at_local(event.position())
        if sq:
            self.square_clicked.emit(sq)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if self._enabled:
            if self._region is None:
                logger.warning("Overlay enabled without board geometry")
            self._apply_clickthrough()
            self.show()
            self.raise_()
            self._apply_clickthrough()
        else:
            self.hide()

    def toggle(self) -> bool:
        self.set_enabled(not self._enabled)
        return self._enabled

    def force_disable(self) -> None:
        """Emergency off — call on startup / crash recovery."""
        self._enabled = False
        self._arrows.clear()
        try:
            self.hide()
        except Exception:  # noqa: BLE001
            pass

    def _apply_clickthrough(self) -> None:
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, not self._interactive
        )
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            if hwnd == 0:
                return
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            WS_EX_TOOLWINDOW = 0x80
            WS_EX_NOACTIVATE = 0x08000000
            user32 = ctypes.windll.user32
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                get_long = user32.GetWindowLongPtrW
                set_long = user32.SetWindowLongPtrW
            else:
                get_long = user32.GetWindowLongW
                set_long = user32.SetWindowLongW
            style = get_long(hwnd, GWL_EXSTYLE)
            style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            if self._interactive:
                # Receive clicks (no focus steal via NOACTIVATE)
                style &= ~WS_EX_TRANSPARENT
            else:
                style |= WS_EX_TRANSPARENT
            set_long(hwnd, GWL_EXSTYLE, style)
            # Critical: hide this window from screen capture (mss/BitBlt), otherwise
            # the capture pipeline sees our own arrows as board changes and
            # auto-applies the suggested move. Win10 2004+.
            WDA_EXCLUDEFROMCAPTURE = 0x11
            if not user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
                logger.warning(
                    "SetWindowDisplayAffinity failed — overlay arrows may be "
                    "visible to capture; keep overlay off during detection"
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("click-through setup failed: %s", exc)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_clickthrough()

    def _to_local(self, screen_x: float, screen_y: float) -> QPointF:
        geo = self.geometry()
        return QPointF(screen_x - geo.x(), screen_y - geo.y())

    def _square_screen_center(self, square: str) -> Optional[QPointF]:
        if not self._region or not self._calibration or not self._grid:
            return None
        try:
            bx, by = self._grid.cell_center_square(square)
            ix, iy = self._calibration.board_xy_to_image(bx, by)
            sx = self._region.left + ix
            sy = self._region.top + iy
            return self._to_local(sx, sy)
        except Exception:  # noqa: BLE001
            return None

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._enabled or self._region is None:
            return
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            self._draw_board_squares(painter)
            if self._selected:
                self._draw_square_marker(
                    painter, self._selected, QColor(108, 92, 231, 150)
                )
            self._draw_ghost_pieces(painter)
            self._draw_legal_hints(painter)

            for fr, to, rank in self._arrows:
                p1 = self._square_screen_center(fr)
                p2 = self._square_screen_center(to)
                if p1 is None or p2 is None:
                    continue
                color = QColor(ARROW_COLORS[min(rank, len(ARROW_COLORS) - 1)])
                color.setAlpha(int(255 * self._opacity))
                self._draw_square_marker(
                    painter, fr, QColor(241, 196, 15, int(100 * self._opacity))
                )
                self._draw_square_marker(
                    painter, to, QColor(46, 204, 113, int(100 * self._opacity))
                )
                pen = QPen(
                    color,
                    float(self._thickness),
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
                painter.setPen(pen)
                painter.setBrush(color)
                painter.drawLine(p1, p2)
                self._arrow_head(painter, p1, p2, color)

            if self._label or self._eval:
                painter.setPen(QColor(255, 255, 255, 230))
                painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
                text = self._label
                if self._eval:
                    text = f"{text}  |  {self._eval}" if text else self._eval
                painter.drawText(QPoint(12, 22), text)

            painter.end()
        except Exception as exc:  # noqa: BLE001
            logger.exception("overlay paint failed: %s", exc)

    def _draw_ghost_pieces(self, painter: QPainter) -> None:
        """Translucent copy of the program's board over the real game board."""
        if (
            self._position is None
            or not self._grid
            or not self._calibration
            or not self._region
            or self._ghost_opacity <= 0.0
        ):
            return
        alpha = max(20, min(160, int(255 * self._ghost_opacity)))
        for sq in chess.SQUARES:
            piece = self._position.piece_at(sq)
            if piece is None:
                continue
            name = chess.square_name(sq)
            try:
                x0, y0, x1, y1 = self._grid.cell_rect_square(name)
                pts = []
                for bx, by in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                    ix, iy = self._calibration.board_xy_to_image(bx, by)
                    pts.append(
                        self._to_local(self._region.left + ix, self._region.top + iy)
                    )
            except Exception:  # noqa: BLE001
                continue
            cx = sum(p.x() for p in pts) / 4.0
            cy = sum(p.y() for p in pts) / 4.0
            top_mid = (pts[0].y() + pts[1].y()) / 2.0
            bot_mid = (pts[2].y() + pts[3].y()) / 2.0
            h = max(10.0, abs(bot_mid - top_mid))
            symbol = PIECE_UNICODE.get(piece.symbol(), piece.symbol())
            painter.setFont(QFont("Segoe UI Symbol", max(8, int(h * 0.55))))
            if piece.color == chess.WHITE:
                painter.setPen(QColor(255, 255, 255, alpha))
            else:
                painter.setPen(QColor(0, 0, 0, min(255, alpha + 40)))
            painter.drawText(
                QRectF(cx - h, cy - h, h * 2.0, h * 2.0),
                Qt.AlignmentFlag.AlignCenter,
                symbol,
            )

    def _board_to_local(self, bx: float, by: float) -> QPointF:
        ix, iy = self._calibration.board_xy_to_image(bx, by)
        return self._to_local(self._region.left + ix, self._region.top + iy)

    def _draw_board_squares(self, painter: QPainter) -> None:
        """Faint translucent chessboard + grid lines over the real board."""
        if not (
            self._show_grid and self._grid and self._calibration and self._region
        ):
            return
        for sq in chess.SQUARES:
            is_light = (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 1
            tint = (
                QColor(235, 235, 245, 26) if is_light else QColor(18, 18, 32, 48)
            )
            self._draw_square_marker(painter, chess.square_name(sq), tint)
        # grid lines
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        try:
            size = float(self._calibration.warped_size)
            step = size / 8.0
            for i in range(9):
                p = min(size - 1.0, i * step)
                painter.drawLine(self._board_to_local(p, 0), self._board_to_local(p, size - 1))
                painter.drawLine(self._board_to_local(0, p), self._board_to_local(size - 1, p))
        except Exception:  # noqa: BLE001
            pass

    def _cell_radius(self, square: str) -> float:
        try:
            x0, y0, x1, y1 = self._grid.cell_rect_square(square)
            p0 = self._board_to_local(x0, y0)
            p1 = self._board_to_local(x1, y1)
            diag = ((p1.x() - p0.x()) ** 2 + (p1.y() - p0.y()) ** 2) ** 0.5
            return max(6.0, diag / 2.0 * 0.7)
        except Exception:  # noqa: BLE001
            return 8.0

    def _draw_legal_hints(self, painter: QPainter) -> None:
        """Dots on squares the selected piece can move to; rings for captures."""
        if not self._selected or self._position is None or not self._grid:
            return
        try:
            from_sq = chess.parse_square(self._selected)
        except ValueError:
            return
        for mv in self._position.legal_moves:
            if mv.from_square != from_sq:
                continue
            name = chess.square_name(mv.to_square)
            center = self._square_screen_center(name)
            if center is None:
                continue
            r = self._cell_radius(name)
            if self._position.is_capture(mv):
                painter.setPen(QPen(QColor(231, 76, 60, 220), 3.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(center, r * 0.9, r * 0.9)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(46, 204, 113, 200))
                painter.drawEllipse(center, r * 0.34, r * 0.34)

    def _draw_square_marker(self, painter: QPainter, square: str, color: QColor) -> None:
        if not self._grid or not self._calibration or not self._region:
            return
        try:
            x0, y0, x1, y1 = self._grid.cell_rect_square(square)
            pts = []
            for bx, by in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                ix, iy = self._calibration.board_xy_to_image(bx, by)
                pts.append(
                    self._to_local(self._region.left + ix, self._region.top + iy)
                )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF(pts))
        except Exception:  # noqa: BLE001
            return

    def _arrow_head(
        self, painter: QPainter, p1: QPointF, p2: QPointF, color: QColor
    ) -> None:
        import math

        angle = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
        head = 14.0 + self._thickness
        a1 = angle + math.pi * 0.85
        a2 = angle - math.pi * 0.85
        poly = QPolygonF(
            [
                p2,
                QPointF(p2.x() + head * math.cos(a1), p2.y() + head * math.sin(a1)),
                QPointF(p2.x() + head * math.cos(a2), p2.y() + head * math.sin(a2)),
            ]
        )
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(poly)
