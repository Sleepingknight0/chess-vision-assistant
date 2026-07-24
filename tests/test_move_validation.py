"""Move validation tests."""

import chess

from chess_core.move_validate import try_parse_move, validate_uci
from move_detection.candidates import candidates_from_squares


def test_validate_e2e4():
    board = chess.Board()
    assert validate_uci(board, "e2e4")
    assert not validate_uci(board, "e2e5")


def test_parse_san():
    board = chess.Board()
    m = try_parse_move(board, "Nf3")
    assert m is not None
    assert m.uci() == "g1f3"


def test_candidates_simple_pawn():
    board = chess.Board()
    moves = candidates_from_squares(board, ["e2"], ["e4"])
    assert any(m.uci() == "e2e4" for m in moves)
