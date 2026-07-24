"""Castling candidate detection from square sets."""

import chess

from move_detection.candidates import candidates_from_squares


def test_kingside_castle_candidates():
    board = chess.Board("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
    moves = candidates_from_squares(board, ["e1"], ["g1"])
    assert any(m.uci() == "e1g1" for m in moves)
