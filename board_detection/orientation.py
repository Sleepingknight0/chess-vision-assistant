"""Board orientation: rotation and my-pieces-at-bottom mapping."""

from __future__ import annotations

from dataclasses import dataclass


FILES = "abcdefgh"
RANKS = "12345678"


@dataclass
class BoardOrientation:
    """Maps between display grid (col 0 left, row 0 top) and chess squares.

    rotation_deg: clockwise rotation of the *visual* board relative to
    standard white-at-bottom (a1 bottom-left).

    my_pieces_at_bottom: if True, user's pieces appear at the bottom of
    the warped preview (common Roblox view). Combined with user_is_white
    to choose effective flip.
    """

    rotation_deg: int = 0
    my_pieces_at_bottom: bool = True
    user_is_white: bool = True

    def __post_init__(self) -> None:
        if self.rotation_deg not in (0, 90, 180, 270):
            raise ValueError("rotation_deg must be 0, 90, 180, or 270")

    def effective_rotation(self) -> int:
        """Rotation that places a1 correctly for display.

        White at bottom, a-file left → 0.
        If user is black and wants pieces at bottom → 180.
        Then apply user rotation_deg.
        """
        base = 0
        if self.my_pieces_at_bottom and not self.user_is_white:
            base = 180
        elif not self.my_pieces_at_bottom and self.user_is_white:
            base = 180
        return (base + self.rotation_deg) % 360

    def square_to_display(self, square: str) -> tuple[int, int]:
        """Algebraic square → (col, row) with row 0 at top."""
        square = square.lower()
        file_idx = FILES.index(square[0])
        rank_idx = RANKS.index(square[1])
        # Standard display white-bottom: a1 is (0, 7), h1 is (7, 7), a8 is (0, 0)
        col, row = file_idx, 7 - rank_idx
        return self._rotate_display(col, row, self.effective_rotation())

    def display_to_square(self, col: int, row: int) -> str:
        col, row = self._rotate_display(col, row, (360 - self.effective_rotation()) % 360)
        file_idx = col
        rank_idx = 7 - row
        return f"{FILES[file_idx]}{RANKS[rank_idx]}"

    @staticmethod
    def _rotate_display(col: int, row: int, deg: int) -> tuple[int, int]:
        """Rotate coordinates within 8×8 grid clockwise around center."""
        for _ in range((deg // 90) % 4):
            col, row = 7 - row, col
        return col, row


def square_from_display(
    col: int, row: int, orientation: BoardOrientation | None = None
) -> str:
    ori = orientation or BoardOrientation()
    return ori.display_to_square(col, row)
