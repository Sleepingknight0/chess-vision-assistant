"""Interactive frame to position the game overlay — drag 4 corners onto the
real game board, no screen capture involved.

Covers the whole virtual desktop while active; emits absolute-screen corner
coordinates (TL, TR, BR, BL) on confirm.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from vision.perspective import PerspectiveCalibration

Point = tuple[float, float]

HANDLE_RADIUS = 10.0
HANDLE_HIT = 22.0
CORNER_LABELS = ("1 ซ้ายบน", "2 ขวาบน", "3 ขวาล่าง", "4 ซ้ายล่าง")


def _virtual_desktop_rect() -> QRect:
    screens = QGuiApplication.screens()
    if not screens:
        return QRect(0, 0, 1920, 1080)
    rect = screens[0].geometry()
    for s in screens[1:]:
        rect = rect.united(s.geometry())
    return rect


class OverlaySetupWindow(QWidget):
    """Full-desktop translucent editor for the overlay's 4 board corners."""

    confirmed = Signal(object)  # list[(x, y)] absolute screen coords TL,TR,BR,BL
    cancelled = Signal()

    def __init__(self, initial_corners_abs: Optional[list[Point]] = None) -> None:
        super().__init__()
        self.setWindowTitle("ตั้งตำแหน่ง Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._desktop = _virtual_desktop_rect()
        self.setGeometry(self._desktop)

        # Local (widget) coordinates for the 4 corners
        if initial_corners_abs:
            self._corners: list[Point] = [
                (x - self._desktop.left(), y - self._desktop.top())
                for x, y in initial_corners_abs
            ]
        else:
            screen = QGuiApplication.primaryScreen()
            geo = screen.availableGeometry() if screen else self._desktop
            cx = geo.center().x() - self._desktop.left()
            cy = geo.center().y() - self._desktop.top()
            half = min(geo.width(), geo.height()) * 0.3
            self._corners = [
                (cx - half, cy - half),
                (cx + half, cy - half),
                (cx + half, cy + half),
                (cx - half, cy + half),
            ]

        self._drag_index: Optional[int] = None
        self._drag_all_from: Optional[QPointF] = None
        self._drag_all_corners: list[Point] = []

        panel = QWidget(self)
        panel.setObjectName("setupPanel")
        panel.setStyleSheet(
            "#setupPanel {background: rgba(20, 22, 30, 235); border-radius: 10px;}"
            "QLabel {color: #e8eaed;} QPushButton {padding: 6px 14px;}"
        )
        pl = QVBoxLayout(panel)
        info = QLabel(
            "ลากมุม 1–4 ให้ตรงมุมกระดานในเกม (ผิวกระดาน ไม่ใช่ขอบไม้)\n"
            "ลากกลางกรอบ = ย้ายทั้งกรอบ · Enter = ยืนยัน · Esc = ยกเลิก"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(info)
        btns = QHBoxLayout()
        ok = QPushButton("ยืนยัน (Enter)")
        ok.setDefault(True)
        ok.clicked.connect(self._confirm)
        cancel = QPushButton("ยกเลิก (Esc)")
        cancel.clicked.connect(self._cancel)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        pl.addLayout(btns)
        panel.adjustSize()
        primary = QGuiApplication.primaryScreen()
        pgeo = primary.availableGeometry() if primary else self._desktop
        panel.move(
            pgeo.center().x() - self._desktop.left() - panel.width() // 2,
            pgeo.top() - self._desktop.top() + 24,
        )

    # ------------------------------------------------------------------

    def corners_abs(self) -> list[Point]:
        return [
            (x + self._desktop.left(), y + self._desktop.top())
            for x, y in self._corners
        ]

    def _confirm(self) -> None:
        self.confirmed.emit(self.corners_abs())
        self.close()

    def _cancel(self) -> None:
        self.cancelled.emit()
        self.close()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._confirm()
        elif event.key() == Qt.Key.Key_Escape:
            self._cancel()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 70))

        quad = QPolygonF([QPointF(x, y) for x, y in self._corners])
        painter.setPen(QPen(QColor(46, 204, 113, 235), 2.5))
        painter.setBrush(QColor(46, 204, 113, 26))
        painter.drawPolygon(quad)

        # Projected 8×8 grid so the user can line up squares, not just edges
        try:
            cal = PerspectiveCalibration(
                corners=list(self._corners), warped_size=512
            )
            painter.setPen(QPen(QColor(241, 196, 15, 150), 1.2))
            for i in range(1, 8):
                p = i * 64.0
                x1, y1 = cal.board_xy_to_image(p, 0)
                x2, y2 = cal.board_xy_to_image(p, 511)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
                x1, y1 = cal.board_xy_to_image(0, p)
                x2, y2 = cal.board_xy_to_image(511, p)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        except Exception:  # noqa: BLE001 — degenerate quad while dragging
            pass

        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        for i, (x, y) in enumerate(self._corners):
            painter.setPen(QPen(QColor(255, 255, 255, 240), 2))
            painter.setBrush(QColor(231, 76, 60, 230))
            painter.drawEllipse(QPointF(x, y), HANDLE_RADIUS, HANDLE_RADIUS)
            painter.drawText(QPointF(x + 14, y - 10), CORNER_LABELS[i])
        painter.end()

    # ------------------------------------------------------------------

    def _hit_corner(self, pos: QPointF) -> Optional[int]:
        for i, (x, y) in enumerate(self._corners):
            if (QPointF(x, y) - pos).manhattanLength() <= HANDLE_HIT:
                return i
        return None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        idx = self._hit_corner(pos)
        if idx is not None:
            self._drag_index = idx
            return
        quad = QPolygonF([QPointF(x, y) for x, y in self._corners])
        if quad.containsPoint(pos, Qt.FillRule.OddEvenFill):
            self._drag_all_from = pos
            self._drag_all_corners = list(self._corners)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        if self._drag_index is not None:
            self._corners[self._drag_index] = (pos.x(), pos.y())
            self.update()
        elif self._drag_all_from is not None:
            dx = pos.x() - self._drag_all_from.x()
            dy = pos.y() - self._drag_all_from.y()
            self._corners = [
                (x + dx, y + dy) for x, y in self._drag_all_corners
            ]
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_index = None
        self._drag_all_from = None
