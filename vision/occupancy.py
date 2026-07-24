"""Occupancy detection via per-cell visual scores + relative deltas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from board_detection.orientation import BoardOrientation
from vision.grid import BoardGrid


@dataclass
class OccupancyResult:
    """occupied[row_display][col_display] — row 0 top."""

    occupied: list[list[bool]]
    scores: list[list[float]] = field(default_factory=list)
    confidence: float = 0.0

    def at(self, row: int, col: int) -> bool:
        return self.occupied[row][col]

    def as_square_map(self, orientation: BoardOrientation) -> dict[str, bool]:
        out: dict[str, bool] = {}
        for r in range(8):
            for c in range(8):
                sq = orientation.display_to_square(c, r)
                out[sq] = self.occupied[r][c]
        return out

    def bitcount(self) -> int:
        return sum(1 for row in self.occupied for v in row if v)

    def score_at_square(self, square: str, orientation: BoardOrientation) -> float:
        col, row = orientation.square_to_display(square)
        if not self.scores:
            return 0.0
        return float(self.scores[row][col])


class OccupancyDetector:
    """Per-cell visual activity score for 3D boards (Roblox-friendly).

    Primary signal for move detection is **score delta** between two frames,
    not absolute occupied/empty thresholds (those fail on pink/blue skins).
    """

    def __init__(
        self,
        threshold: float = 0.28,
        center_fraction: float = 0.62,
        delta_threshold: float = 0.10,
    ) -> None:
        self.threshold = threshold
        self.center_fraction = center_fraction
        self.delta_threshold = delta_threshold
        self._ref_scores: Optional[list[list[float]]] = None

    def reset_baseline(self) -> None:
        self._ref_scores = None

    def set_reference_scores(self, scores: list[list[float]]) -> None:
        self._ref_scores = [row[:] for row in scores]

    def score_frame(
        self, warped_bgr: np.ndarray, orientation: BoardOrientation | None = None
    ) -> list[list[float]]:
        return self._score_cells(warped_bgr, orientation)

    def detect(
        self,
        warped_bgr: np.ndarray,
        orientation: BoardOrientation | None = None,
    ) -> OccupancyResult:
        scores = self._score_cells(warped_bgr, orientation)
        occupied: list[list[bool]] = []
        confs: list[float] = []
        for r in range(8):
            row_occ: list[bool] = []
            for c in range(8):
                s = scores[r][c]
                thr = self.threshold
                if self._ref_scores is not None:
                    # Adaptive: mid-point between empty-ish and occupied-ish cells is hard;
                    # use absolute score with lower threshold for 3D pieces.
                    thr = max(0.18, min(self.threshold, self._ref_scores[r][c] * 0.55 + 0.12))
                occ = s >= thr
                row_occ.append(occ)
                confs.append(min(1.0, abs(s - thr) / max(thr, 0.12)))
            occupied.append(row_occ)
        return OccupancyResult(
            occupied=occupied, scores=scores, confidence=float(np.mean(confs)) if confs else 0.0
        )

    def delta_map(
        self,
        before_scores: list[list[float]],
        after_scores: list[list[float]],
        delta_threshold: float | None = None,
    ) -> tuple[list[tuple[int, int]], list[tuple[int, int]], list[list[float]]]:
        """Return (decreased cells, increased cells, delta grid) as display (col,row)."""
        thr = self.delta_threshold if delta_threshold is None else delta_threshold
        decreased: list[tuple[int, int]] = []
        increased: list[tuple[int, int]] = []
        deltas: list[list[float]] = []
        for r in range(8):
            drow: list[float] = []
            for c in range(8):
                d = float(after_scores[r][c] - before_scores[r][c])
                drow.append(d)
                if d <= -thr:
                    decreased.append((c, r))
                elif d >= thr:
                    increased.append((c, r))
            deltas.append(drow)
        return decreased, increased, deltas

    def compare(
        self, before: OccupancyResult, after: OccupancyResult
    ) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        emptied: list[tuple[int, int]] = []
        filled: list[tuple[int, int]] = []
        for r in range(8):
            for c in range(8):
                b = before.at(r, c)
                a = after.at(r, c)
                if b and not a:
                    emptied.append((c, r))
                if a and not b:
                    filled.append((c, r))
        return emptied, filled

    def _score_cells(
        self, warped_bgr: np.ndarray, orientation: BoardOrientation | None
    ) -> list[list[float]]:
        h, w = warped_bgr.shape[:2]
        size = min(h, w)
        ori = orientation or BoardOrientation()
        grid = BoardGrid(size=size, orientation=ori)
        gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY)
        # Stronger edges for 3D mesh pieces
        edges = cv2.Canny(gray, 30, 100)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        residual = cv2.absdiff(gray, blur)
        # Local contrast
        lap = cv2.Laplacian(gray, cv2.CV_32F)
        lap_abs = np.abs(lap)

        scores: list[list[float]] = []
        for row in range(8):
            row_s: list[float] = []
            for col in range(8):
                x0, y0, x1, y1 = grid.cell_rect_display(col, row)
                cell_g = gray[y0:y1, x0:x1]
                cell_e = edges[y0:y1, x0:x1]
                cell_r = residual[y0:y1, x0:x1]
                cell_l = lap_abs[y0:y1, x0:x1]
                if cell_g.size == 0:
                    row_s.append(0.0)
                    continue
                ch, cw = cell_g.shape[:2]
                mx = int(cw * (1.0 - self.center_fraction) / 2)
                my = int(ch * (1.0 - self.center_fraction) / 2)
                if mx * 2 < cw and my * 2 < ch:
                    cell_g = cell_g[my : ch - my, mx : cw - mx]
                    cell_e = cell_e[my : ch - my, mx : cw - mx]
                    cell_r = cell_r[my : ch - my, mx : cw - mx]
                    cell_l = cell_l[my : ch - my, mx : cw - mx]
                edge_density = float(np.mean(cell_e)) / 255.0
                variance = float(np.std(cell_g.astype(np.float32))) / 50.0
                residual_m = float(np.mean(cell_r)) / 35.0
                lap_m = float(np.mean(cell_l)) / 25.0
                score = (
                    0.40 * edge_density
                    + 0.25 * min(variance, 1.6)
                    + 0.20 * min(residual_m, 1.6)
                    + 0.15 * min(lap_m, 1.6)
                )
                row_s.append(float(min(score, 2.0)))
            scores.append(row_s)
        return scores
