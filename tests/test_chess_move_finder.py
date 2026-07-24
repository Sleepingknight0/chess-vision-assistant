"""Unit tests for chess-logic move finder (no vision)."""

import chess

from move_detection.chess_move_finder import find_moves


def test_e2_left_e4_arrive():
    board = chess.Board()
    left = {f"{f}2": 1.0 for f in "abcdefgh"}
    left["e2"] = 40.0
    arrive = {"e4": 35.0, "e3": 5.0, "d4": 2.0}
    cands = find_moves(board, left_scores=left, arrive_scores=arrive)
    assert cands
    assert cands[0].move.uci() == "e2e4"


def test_knight_g1_only_legal_dests():
    board = chess.Board()
    left = {"g1": 50.0}
    # noise on illegal square a3
    arrive = {"f3": 30.0, "a3": 80.0, "h3": 10.0}
    cands = find_moves(board, left_scores=left, arrive_scores=arrive)
    assert cands
    # a3 is illegal for Ng1 — must not win
    assert cands[0].move.uci() in ("g1f3", "g1h3", "g1e2")
    assert cands[0].move.uci() != "g1a3"
    assert all(c.move.from_square == chess.G1 for c in cands[:5])


def test_capture_pattern():
    board = chess.Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2")
    left = {"e4": 40.0}
    arrive = {"d5": 38.0}
    cands = find_moves(board, left_scores=left, arrive_scores=arrive)
    assert any(c.move.uci() == "e4d5" for c in cands)
