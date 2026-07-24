"""Integration tests: vision heat + chess logic finder."""

import chess
import numpy as np

from board_detection.orientation import BoardOrientation
from move_detection.auto_tracker import AutoMoveTracker


def _board_img(size: int = 512) -> np.ndarray:
    img = np.zeros((size, size, 3), dtype=np.uint8)
    cs = size // 8
    for r in range(8):
        for c in range(8):
            color = (200, 180, 220) if (r + c) % 2 == 0 else (90, 70, 120)
            img[r * cs : (r + 1) * cs, c * cs : (c + 1) * cs] = color
    return img


def _blob(img: np.ndarray, col: int, row: int, bgr=(240, 240, 240)) -> None:
    size = img.shape[0]
    cs = size // 8
    m = cs // 5
    img[row * cs + m : (row + 1) * cs - m, col * cs + m : (col + 1) * cs - m] = bgr


def _paint_start(img: np.ndarray, ori: BoardOrientation) -> None:
    for f in "abcdefgh":
        for rank, color in (
            (2, (230, 230, 230)),
            (1, (220, 220, 220)),
            (7, (40, 40, 90)),
            (8, (30, 30, 70)),
        ):
            c, r = ori.square_to_display(f"{f}{rank}")
            _blob(img, c, r, color)


def test_e2e4_logic_vision():
    ori = BoardOrientation()
    t = AutoMoveTracker(orientation=ori, accept_score=8.0, confirm_hits=1)
    board = chess.Board()
    before = _board_img()
    _paint_start(before, ori)
    t.lock(before)
    after = before.copy()
    ec, er = ori.square_to_display("e2")
    fc, fr = ori.square_to_display("e4")
    cs = 64
    after[er * cs : (er + 1) * cs, ec * cs : (ec + 1) * cs] = (90, 70, 120)
    _blob(after, fc, fr, (230, 230, 230))
    res = t.force_best(after, board)
    assert res.move is not None, res.message
    assert res.move.uci() == "e2e4", (res.move.uci(), res.all_top, res.message)
    assert "e2" in res.message and "e4" in res.message


def test_knight_not_illegal():
    ori = BoardOrientation()
    t = AutoMoveTracker(orientation=ori, accept_score=5.0, confirm_hits=1)
    board = chess.Board()
    before = _board_img()
    _paint_start(before, ori)
    t.lock(before)
    after = before.copy()
    gc, gr = ori.square_to_display("g1")
    fc, fr = ori.square_to_display("f3")
    ac, ar = ori.square_to_display("a3")
    cs = 64
    after[gr * cs : (gr + 1) * cs, gc * cs : (gc + 1) * cs] = (90, 70, 120)
    _blob(after, fc, fr, (200, 200, 200))
    _blob(after, ac, ar, (0, 255, 0))  # strong noise illegal
    res = t.force_best(after, board)
    assert res.move is not None
    assert res.move.from_square == chess.G1
    assert res.move.uci() in ("g1f3", "g1h3", "g1e2")


def test_cursor_hover_does_not_invent_move():
    """Only the from-square changes (e.g. cursor on a piece) — no move allowed."""
    ori = BoardOrientation()
    t = AutoMoveTracker(orientation=ori, accept_score=8.0, confirm_hits=1)
    board = chess.Board()
    before = _board_img()
    _paint_start(before, ori)
    t.lock(before)

    after = before.copy()
    ec, er = ori.square_to_display("e2")
    _blob(after, ec, er, (60, 200, 255))  # e2 recolored, no destination changes

    res = t.force_best(after, board)
    assert res.move is None, (res.move and res.move.uci(), res.message)


def test_mid_animation_not_confirmed_then_settled_confirms():
    """Frames during the piece slide must not confirm; settled frames must."""
    ori = BoardOrientation()
    t = AutoMoveTracker(orientation=ori, accept_score=8.0, confirm_hits=2)
    board = chess.Board()
    before = _board_img()
    _paint_start(before, ori)
    t.lock(before)
    for _ in range(3):  # burn post-lock cooldown frames
        t.observe(before, board)

    cs = 64
    ec, er = ori.square_to_display("e2")
    empty_e2 = (200, 180, 220) if (er + ec) % 2 == 0 else (90, 70, 120)

    # Mid-animation: e2 already empty, piece currently passing over e3
    mid = before.copy()
    mid[er * cs : (er + 1) * cs, ec * cs : (ec + 1) * cs] = empty_e2
    mc, mr = ori.square_to_display("e3")
    _blob(mid, mc, mr, (230, 230, 230))
    r1 = t.observe(mid, board)
    assert "พร้อมยืนยัน" not in r1.message, r1.message

    # Settled: e2 empty, piece landed on e4
    settled = before.copy()
    settled[er * cs : (er + 1) * cs, ec * cs : (ec + 1) * cs] = empty_e2
    fc, fr = ori.square_to_display("e4")
    _blob(settled, fc, fr, (230, 230, 230))

    r2 = t.observe(settled, board)  # heat still differs from the mid frame
    assert "พร้อมยืนยัน" not in r2.message, r2.message

    ready = r2
    for _ in range(3):  # stable frames: must confirm within a few observes
        ready = t.observe(settled, board)
        if "พร้อมยืนยัน" in ready.message:
            break
    assert "พร้อมยืนยัน" in ready.message, ready.message
    assert ready.move is not None and ready.move.uci() == "e2e4", (
        ready.move and ready.move.uci(),
        ready.message,
    )
