"""Interactive 4-corner editor on a source ROI image."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from vision.perspective import PerspectiveCalibration, default_corners


class CornerEditor(QWidget):
    corners_changed = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(360, 360)
        self._image: Optional[np.ndarray] = None
        self._corners: list[tuple[float, float]] = []
        self._drag_idx: Optional[int] = None
        self._scale = 1.0
        self._offset = (0.0, 0.0)
        self.setMouseTracking(True)

    def set_image(self, bgr: Optional[np.ndarray]) -> None:
        self._image = bgr
        if bgr is not None and (not self._corners):
            h, w = bgr.shape[:2]
            self._corners = default_corners(float(w), float(h))
        self.update()

    def set_corners(self, corners: list[tuple[float, float]] | list[list[float]]) -> None:
        self._corners = [(float(c[0]), float(c[1])) for c in corners]
        self.update()

    def corners(self) -> list[tuple[float, float]]:
        return list(self._corners)

    def calibration(self, warped_size: int = 512) -> PerspectiveCalibration:
        return PerspectiveCalibration(corners=list(self._corners), warped_size=warped_size)

    def _compute_transform(self) -> None:
        if self._image is None:
            return
        h, w = self._image.shape[:2]
        if w == 0 or h == 0:
            return
        sx = self.width() / w
        sy = self.height() / h
        self._scale = min(sx, sy)
        dw = w * self._scale
        dh = h * self._scale
        self._offset = ((self.width() - dw) / 2, (self.height() - dh) / 2)

    def _img_to_widget(self, x: float, y: float) -> QPointF:
        ox, oy = self._offset
        return QPointF(ox + x * self._scale, oy + y * self._scale)

    def _widget_to_img(self, x: float, y: float) -> tuple[float, float]:
        ox, oy = self._offset
        return (x - ox) / self._scale, (y - oy) / self._scale

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(13, 15, 20))
        if self._image is None:
            painter.setPen(QColor(154, 160, 166))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Capture ROI first, then adjust the 4 corners")
            painter.end()
            return

        self._compute_transform()
        rgb = cv2.cvtColor(self._image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        pix = QPixmap.fromImage(qimg)
        dw = int(w * self._scale)
        dh = int(h * self._scale)
        ox, oy = self._offset
        painter.drawPixmap(int(ox), int(oy), dw, dh, pix)

        if len(self._corners) == 4:
            pen = QPen(QColor(108, 92, 231), 2)
            painter.setPen(pen)
            pts = [self._img_to_widget(x, y) for x, y in self._corners]
            for i in range(4):
                painter.drawLine(pts[i], pts[(i + 1) % 4])
            labels = ["Top-left", "Top-right", "Bottom-right", "Bottom-left"]
            colors = [
                QColor(241, 196, 15),
                QColor(46, 204, 113),
                QColor(52, 152, 219),
                QColor(231, 76, 60),
            ]
            for i, (pt, lab) in enumerate(zip(pts, labels)):
                painter.setBrush(colors[i])
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.drawEllipse(pt, 10, 10)
                painter.drawText(pt + QPointF(12, -8), lab)

        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._image is None or len(self._corners) != 4:
            return
        pos = event.position()
        best = None
        best_d = 18.0
        for i, (x, y) in enumerate(self._corners):
            wp = self._img_to_widget(x, y)
            d = (wp.x() - pos.x()) ** 2 + (wp.y() - pos.y()) ** 2
            if d < best_d * best_d:
                best_d = d ** 0.5
                best = i
        self._drag_idx = best

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_idx is None or self._image is None:
            return
        ix, iy = self._widget_to_img(event.position().x(), event.position().y())
        h, w = self._image.shape[:2]
        ix = max(0.0, min(float(w - 1), ix))
        iy = max(0.0, min(float(h - 1), iy))
        self._corners[self._drag_idx] = (ix, iy)
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_idx is not None:
            self._drag_idx = None
            self.corners_changed.emit(self.corners())
