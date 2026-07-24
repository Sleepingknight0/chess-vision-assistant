"""Board drift detection — warn when calibration no longer matches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from vision.perspective import PerspectiveCalibration


@dataclass
class DriftResult:
    drifted: bool
    score: float
    message: str


class DriftDetector:
    """Compare edge energy near expected board border after warp."""

    def __init__(self, threshold: float = 0.35) -> None:
        self.threshold = threshold
        self._ref_border: Optional[np.ndarray] = None

    def set_reference(self, warped_bgr: np.ndarray) -> None:
        self._ref_border = self._border_signature(warped_bgr)

    def check(self, warped_bgr: np.ndarray) -> DriftResult:
        if self._ref_border is None:
            self.set_reference(warped_bgr)
            return DriftResult(False, 0.0, "")
        cur = self._border_signature(warped_bgr)
        # Normalize correlation distance
        a = self._ref_border.astype(np.float32)
        b = cur.astype(np.float32)
        a = (a - a.mean()) / (a.std() + 1e-6)
        b = (b - b.mean()) / (b.std() + 1e-6)
        corr = float(np.mean(a * b))
        dist = 1.0 - max(-1.0, min(1.0, corr))
        if dist > self.threshold:
            return DriftResult(
                True,
                dist,
                "Board position changed — please recalibrate",
            )
        return DriftResult(False, dist, "")

    @staticmethod
    def _border_signature(warped_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (64, 64))
        edges = cv2.Canny(gray, 50, 150)
        # outer ring
        mask = np.zeros_like(edges)
        mask[:4, :] = 1
        mask[-4:, :] = 1
        mask[:, :4] = 1
        mask[:, -4:] = 1
        return (edges * mask).astype(np.float32).ravel()


def try_auto_recalibrate_corners(
    roi_bgr: np.ndarray, current: PerspectiveCalibration
) -> Optional[PerspectiveCalibration]:
    """Very conservative auto corner snap using largest quad contour.

    Returns new calibration only if a confident quad is found; else None.
    """
    try:
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        h, w = gray.shape[:2]
        best = None
        best_area = 0.0
        for cnt in contours:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) != 4:
                continue
            area = cv2.contourArea(approx)
            if area < 0.2 * w * h:
                continue
            if area > best_area:
                best_area = area
                best = approx.reshape(4, 2).astype(np.float32)
        if best is None:
            return None
        # order TL, TR, BR, BL
        ordered = _order_quad(best)
        return PerspectiveCalibration(
            corners=[(float(x), float(y)) for x, y in ordered],
            warped_size=current.warped_size,
        )
    except Exception:
        return None


def _order_quad(pts: np.ndarray) -> np.ndarray:
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).ravel()
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)
