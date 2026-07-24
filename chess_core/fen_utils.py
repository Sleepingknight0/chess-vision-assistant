"""FEN helpers."""

from __future__ import annotations

import chess


STARTING_FEN = chess.STARTING_FEN


def starting_fen() -> str:
    return STARTING_FEN


def is_valid_fen(fen: str) -> bool:
    try:
        chess.Board(fen.strip())
        return True
    except ValueError:
        return False


def normalize_fen(fen: str) -> str:
    """Return canonical FEN or raise ValueError."""
    board = chess.Board(fen.strip())
    return board.fen()


def board_from_fen(fen: str) -> chess.Board:
    return chess.Board(fen.strip())
