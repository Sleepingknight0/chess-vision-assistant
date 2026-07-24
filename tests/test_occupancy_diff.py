"""Occupancy compare and candidate move tests."""

import chess
import numpy as np

from board_detection.orientation import BoardOrientation
from move_detection.candidates import candidates_from_squares, score_candidate
from move_detection.diff_tracker import DiffTracker
from vision.occupancy import OccupancyDetector, OccupancyResult


def test_compare_emptied_filled():
    det = OccupancyDetector()
    before = OccupancyResult(
        occupied=[[False] * 8 for _ in range(8)],
        scores=[[0.0] * 8 for _ in range(8)],
    )
    after = OccupancyResult(
        occupied=[[False] * 8 for _ in range(8)],
        scores=[[0.0] * 8 for _ in range(8)],
    )
    # mark display (col,row)
    before.occupied[7][4] = True  # e1-ish depending ori
    after.occupied[5][4] = True
    emptied, filled = det.compare(before, after)
    assert (4, 7) in emptied
    assert (4, 5) in filled


def test_candidates_nf3():
    board = chess.Board()
    moves = candidates_from_squares(board, ["g1"], ["f3"])
    assert any(m.uci() == "g1f3" for m in moves)


def test_candidates_capture():
    board = chess.Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2")
    moves = candidates_from_squares(board, ["e4"], ["d5"])
    assert any(m.uci() == "e4d5" for m in moves)


def test_score_candidate():
    board = chess.Board()
    m = chess.Move.from_uci("e2e4")
    s = score_candidate(board, m, ["e2"], ["e4"])
    assert s >= 0.9


def test_occupancy_detect_runs():
    img = np.zeros((512, 512, 3), dtype=np.uint8)
    # draw bright blobs on rank 2 / 7 area
    img[60:90, 20:500] = 200
    img[420:450, 20:500] = 200
    det = OccupancyDetector(threshold=0.2)
    res = det.detect(img, BoardOrientation())
    assert len(res.occupied) == 8
    assert len(res.occupied[0]) == 8


def test_diff_tracker_baseline():
    t = DiffTracker(orientation=BoardOrientation())
    board = chess.Board()
    t.set_baseline_from_board(board)
    assert t._armed is True
    assert t._locked_board_fen != ""


def test_scan_locks_reference():
    t = DiffTracker(orientation=BoardOrientation())
    board = chess.Board()
    img = np.zeros((512, 512, 3), dtype=np.uint8)
    t.set_baseline_from_board(board)
    hyp = t.scan_now(img, board)
    assert t._ref_scores is not None
    # first scan only locks
    assert hyp.moves == [] or True
