"""4-corner perspective transform for 3D board → top-down square."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import cv2
import numpy as np


Point = tuple[float, float]


def default_corners(width: float, height: float, margin: float = 0.08) -> list[Point]:
    """Default corners inset from ROI edges: TL, TR, BR, BL."""
    mx = width * margin
    my = height * margin
    return [
        (mx, my),
        (width - mx, my),
        (width - mx, height - my),
        (mx, height - my),
    ]


@dataclass
class PerspectiveCalibration:
    """Perspective calibration in ROI image coordinates (pixels).

    Corners order: top-left, top-right, bottom-right, bottom-left.
    """

    corners: list[Point] = field(default_factory=list)
    warped_size: int = 512

    def __post_init__(self) -> None:
        if not self.corners:
            self.corners = default_corners(float(self.warped_size), float(self.warped_size))
        if len(self.corners) != 4:
            raise ValueError("Exactly 4 corners required (TL, TR, BR, BL)")

    def src_points(self) -> np.ndarray:
        return np.array(self.corners, dtype=np.float32)

    def dst_points(self) -> np.ndarray:
        s = float(self.warped_size)
        return np.array(
            [[0.0, 0.0], [s - 1, 0.0], [s - 1, s - 1], [0.0, s - 1]],
            dtype=np.float32,
        )

    def matrix(self) -> np.ndarray:
        return cv2.getPerspectiveTransform(self.src_points(), self.dst_points())

    def inverse_matrix(self) -> np.ndarray:
        return cv2.getPerspectiveTransform(self.dst_points(), self.src_points())

    def warp(self, image: np.ndarray, size: int | None = None) -> np.ndarray:
        out = size or self.warped_size
        if out != self.warped_size:
            cal = PerspectiveCalibration(corners=list(self.corners), warped_size=out)
            m = cal.matrix()
        else:
            m = self.matrix()
        return cv2.warpPerspective(image, m, (out, out))

    def image_to_board_xy(self, x: float, y: float) -> Point:
        """Map ROI image pixel → warped board pixel."""
        pts = np.array([[[x, y]]], dtype=np.float32)
        out = cv2.perspectiveTransform(pts, self.matrix())
        return float(out[0, 0, 0]), float(out[0, 0, 1])

    def board_xy_to_image(self, x: float, y: float) -> Point:
        """Map warped board pixel → ROI image pixel (for overlay)."""
        pts = np.array([[[x, y]]], dtype=np.float32)
        out = cv2.perspectiveTransform(pts, self.inverse_matrix())
        return float(out[0, 0, 0]), float(out[0, 0, 1])

    def set_corner(self, index: int, point: Point) -> None:
        if index < 0 or index > 3:
            raise IndexError("corner index must be 0..3")
        self.corners[index] = (float(point[0]), float(point[1]))

    def as_list(self) -> list[list[float]]:
        return [[float(x), float(y)] for x, y in self.corners]

    @classmethod
    def from_list(
        cls, corners: Sequence[Sequence[float]], warped_size: int = 512
    ) -> PerspectiveCalibration:
        pts = [(float(p[0]), float(p[1])) for p in corners]
        return cls(corners=pts, warped_size=warped_size)
