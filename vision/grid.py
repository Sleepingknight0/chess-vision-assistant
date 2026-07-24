"""8×8 board grid on warped top-down image."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np

from board_detection.orientation import BoardOrientation, square_from_display


FILES = "abcdefgh"
RANKS = "12345678"


def square_name_to_index(name: str) -> tuple[int, int]:
    """Return (file_idx 0-7, rank_idx 0-7) for algebraic square."""
    name = name.strip().lower()
    if len(name) != 2 or name[0] not in FILES or name[1] not in RANKS:
        raise ValueError(f"Invalid square: {name}")
    return FILES.index(name[0]), RANKS.index(name[1])


def index_to_square_name(file_idx: int, rank_idx: int) -> str:
    return f"{FILES[file_idx]}{RANKS[rank_idx]}"


@dataclass
class BoardGrid:
    """Divide a square warped board image into 64 cells."""

    size: int = 512
    orientation: BoardOrientation | None = None

    def __post_init__(self) -> None:
        if self.orientation is None:
            self.orientation = BoardOrientation()

    @property
    def cell_size(self) -> float:
        return self.size / 8.0

    def cell_rect_display(self, col: int, row: int) -> tuple[int, int, int, int]:
        """Pixel rect for display cell (col 0 left, row 0 top) → x0,y0,x1,y1."""
        cs = self.cell_size
        x0 = int(round(col * cs))
        y0 = int(round(row * cs))
        x1 = int(round((col + 1) * cs))
        y1 = int(round((row + 1) * cs))
        return x0, y0, x1, y1

    def cell_center_display(self, col: int, row: int) -> tuple[float, float]:
        x0, y0, x1, y1 = self.cell_rect_display(col, row)
        return (x0 + x1) / 2.0, (y0 + y1) / 2.0

    def cell_rect_square(self, square: str) -> tuple[int, int, int, int]:
        assert self.orientation is not None
        col, row = self.orientation.square_to_display(square)
        return self.cell_rect_display(col, row)

    def cell_center_square(self, square: str) -> tuple[float, float]:
        assert self.orientation is not None
        col, row = self.orientation.square_to_display(square)
        return self.cell_center_display(col, row)

    def display_to_square(self, col: int, row: int) -> str:
        assert self.orientation is not None
        return self.orientation.display_to_square(col, row)

    def square_at_pixel(self, x: float, y: float) -> str:
        cs = self.cell_size
        col = int(x // cs)
        row = int(y // cs)
        col = max(0, min(7, col))
        row = max(0, min(7, row))
        return self.display_to_square(col, row)

    def iter_cells(self) -> Iterator[tuple[str, tuple[int, int, int, int]]]:
        for row in range(8):
            for col in range(8):
                sq = self.display_to_square(col, row)
                yield sq, self.cell_rect_display(col, row)

    def crop_cell(
        self, warped: np.ndarray, square: str, center_fraction: float = 0.6
    ) -> np.ndarray:
        """Crop center region of a cell (reduces 3D piece spillover)."""
        x0, y0, x1, y1 = self.cell_rect_square(square)
        w = x1 - x0
        h = y1 - y0
        mx = int(w * (1.0 - center_fraction) / 2)
        my = int(h * (1.0 - center_fraction) / 2)
        return warped[y0 + my : y1 - my, x0 + mx : x1 - mx].copy()

    def draw_grid(
        self, warped: np.ndarray, color: tuple[int, int, int] = (0, 255, 255), thickness: int = 1
    ) -> np.ndarray:
        import cv2

        out = warped.copy()
        cs = self.cell_size
        for i in range(9):
            p = int(round(i * cs))
            cv2.line(out, (p, 0), (p, self.size - 1), color, thickness)
            cv2.line(out, (0, p), (self.size - 1, p), color, thickness)
        return out
