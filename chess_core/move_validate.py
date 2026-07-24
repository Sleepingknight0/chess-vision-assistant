"""Move parsing and validation helpers."""

from __future__ import annotations

from typing import Optional

import chess


def validate_uci(board: chess.Board, uci: str) -> bool:
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        return False
    return move in board.legal_moves


def try_parse_move(board: chess.Board, text: str) -> Optional[chess.Move]:
    """Parse UCI or SAN; return None if illegal/unparseable."""
    text = text.strip()
    if not text:
        return None
    try:
        move = chess.Move.from_uci(text)
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    try:
        move = board.parse_san(text)
        if move in board.legal_moves:
            return move
    except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError):
        pass
    return None


def is_castling(move: chess.Move, board: chess.Board) -> bool:
    return board.is_castling(move)


def is_en_passant(move: chess.Move, board: chess.Board) -> bool:
    return board.is_en_passant(move)


def is_promotion(move: chess.Move) -> bool:
    return move.promotion is not None
