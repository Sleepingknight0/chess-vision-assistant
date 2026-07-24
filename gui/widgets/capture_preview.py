"""Warped board preview with grid + change heatmap overlay."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from vision.grid import BoardGrid


def bgr_to_qpixmap(bgr: np.ndarray) -> QPixmap:
    if bgr is None or bgr.size == 0:
        return QPixmap()
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w
    qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


class CapturePreview(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._label = QLabel("No image yet")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setMinimumSize(240, 240)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._label.setStyleSheet(
            "background:#0d0f14; border:1px solid #2a2f3a; border-radius:8px; color:#9aa0a6;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self._image: Optional[np.ndarray] = None
        self._heat: Optional[np.ndarray] = None  # 8x8 float
        self._show_grid = True
        self._grid = BoardGrid()

    def set_grid(self, grid: BoardGrid) -> None:
        self._grid = grid
        self._refresh()

    def set_show_grid(self, show: bool) -> None:
        self._show_grid = show
        self._refresh()

    def set_image(self, bgr: Optional[np.ndarray]) -> None:
        self._image = bgr
        self._refresh()

    def set_heat(self, heat: Optional[np.ndarray]) -> None:
        """Optional 8x8 change heatmap (higher = more changed)."""
        self._heat = heat
        self._refresh()

    def _refresh(self) -> None:
        if self._image is None:
            self._label.setPixmap(QPixmap())
            self._label.setText("No image yet")
            return
        img = self._image.copy()
        h, w = img.shape[:2]
        size = min(h, w)

        # Draw heatmap
        if self._heat is not None and self._heat.shape >= (8, 8):
            try:
                mx = float(np.max(self._heat)) + 1e-6
                for row in range(8):
                    for col in range(8):
                        v = float(self._heat[row, col]) / mx
                        if v < 0.15:
                            continue
                        x0 = int(col * size / 8)
                        y0 = int(row * size / 8)
                        x1 = int((col + 1) * size / 8)
                        y1 = int((row + 1) * size / 8)
                        # yellow → red by intensity
                        color = (0, int(80 + 175 * v), int(255 * v))  # BGR
                        overlay = img.copy()
                        cv2.rectangle(overlay, (x0, y0), (x1, y1), color, -1)
                        img = cv2.addWeighted(overlay, 0.35 * v + 0.1, img, 1 - (0.35 * v + 0.1), 0)
            except Exception:
                pass

        if self._show_grid and img.shape[0] == img.shape[1]:
            try:
                self._grid.size = img.shape[0]
                img = self._grid.draw_grid(img)
            except Exception:
                pass

        pix = bgr_to_qpixmap(img)
        self._label.setText("")
        self._label.setPixmap(
            pix.scaled(
                self._label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh()
