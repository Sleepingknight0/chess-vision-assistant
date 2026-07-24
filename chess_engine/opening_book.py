"""Polyglot opening book — instant, theory-perfect opening moves.

While the position is in the book, the recommended move comes straight from
proven opening theory (no thinking needed). As soon as the opponent leaves the
book, the caller falls back to the engine's full search.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import chess
import chess.polyglot

logger = logging.getLogger(__name__)


class OpeningBook:
    def __init__(self, path: str = "") -> None:
        self.path = path
        self.enabled = True

    def set_path(self, path: str) -> None:
        self.path = path or ""

    def available(self) -> bool:
        return self.enabled and bool(self.path) and Path(self.path).is_file()

    def lookup(self, board: chess.Board) -> Optional[chess.Move]:
        """Best (most-proven) book move for this position, or None."""
        if not self.available():
            return None
        try:
            with chess.polyglot.open_reader(self.path) as reader:
                entries = list(reader.find_all(board))
        except Exception as exc:  # noqa: BLE001
            logger.warning("book read failed: %s", exc)
            return None
        if not entries:
            return None
        best = max(entries, key=lambda e: e.weight)
        move = best.move
        return move if move in board.legal_moves else None

    def count(self, board: chess.Board) -> int:
        if not self.available():
            return 0
        try:
            with chess.polyglot.open_reader(self.path) as reader:
                return sum(1 for _ in reader.find_all(board))
        except Exception:  # noqa: BLE001
            return 0
