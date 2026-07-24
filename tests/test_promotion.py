"""Promotion tests."""

import chess

from chess_core.special_moves import apply_and_fen, make_promotion
from chess_core.move_validate import is_promotion


def test_promote_to_queen():
    board, move = make_promotion()
    assert is_promotion(move)
    assert move in board.legal_moves
    apply_and_fen(board, move)
    assert board.piece_at(chess.A8) == chess.Piece.from_symbol("Q")


def test_underpromote_knight():
    board = chess.Board("8/P7/8/8/8/8/8/4K2k w - - 0 1")
    move = chess.Move.from_uci("a7a8n")
    assert move in board.legal_moves
    board.push(move)
    assert board.piece_at(chess.A8).piece_type == chess.KNIGHT
