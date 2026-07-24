"""Fullscreen translucent ROI drag selector."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from capture.base import CaptureRegion


class RegionSelector(QWidget):
    """Fullscreen overlay to drag-select a rectangle on a monitor."""

    region_selected = Signal(object)  # CaptureRegion
    cancelled = Signal()

    def __init__(self, monitor_geometry: QRect, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(monitor_geometry)
        self._origin_geo = monitor_geometry
        self._start: Optional[QPoint] = None
        self._end: Optional[QPoint] = None
        self._dragging = False

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        if self._start and self._end:
            rect = QRect(self._start, self._end).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(108, 92, 231), 2))
            painter.drawRect(rect)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                rect.adjusted(4, 4, 0, 0),
                f"{rect.width()} × {rect.height()}",
            )
        else:
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Drag a box around the chessboard — ESC to cancel",
            )
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._end = self._start
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._end = event.position().toPoint()
            rect = QRect(self._start, self._end).normalized()
            if rect.width() < 20 or rect.height() < 20:
                self.cancelled.emit()
                self.close()
                return
            # Convert widget-local to virtual desktop coords
            left = self._origin_geo.x() + rect.x()
            top = self._origin_geo.y() + rect.y()
            region = CaptureRegion(left, top, rect.width(), rect.height())
            self.region_selected.emit(region)
            self.close()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()


def select_region_on_monitor(monitor_index: int) -> Optional[CaptureRegion]:
    """Blocking-style helper using event loop; prefer signal-based in GUI."""
    screens = QGuiApplication.screens()
    # Map mss index: 0 = virtual all, 1 = first physical ≈ screens[0]
    if monitor_index <= 0:
        geo = QGuiApplication.primaryScreen().geometry()
        for s in screens:
            geo = geo.united(s.geometry())
    else:
        idx = monitor_index - 1
        if idx < 0 or idx >= len(screens):
            idx = 0
        geo = screens[idx].geometry()

    result: dict[str, Optional[CaptureRegion]] = {"region": None}

    selector = RegionSelector(geo)

    def on_sel(r: CaptureRegion) -> None:
        result["region"] = r

    selector.region_selected.connect(on_sel)
    selector.showFullScreen()
    return result  # type: ignore[return-value]
