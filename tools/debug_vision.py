"""Debug pixel-diff detection on real Roblox screenshots."""
from __future__ import annotations

import sys
from pathlib import Path

import chess
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from board_detection.orientation import BoardOrientation
from move_detection.auto_tracker import AutoMoveTracker


def extract_board(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask_pink = cv2.inRange(hsv, (140, 40, 80), (180, 255, 255))
    mask_blue = cv2.inRange(hsv, (90, 40, 40), (140, 255, 200))
    mask_purp = cv2.inRange(hsv, (120, 30, 40), (160, 255, 220))
    mask = cv2.bitwise_or(mask_pink, cv2.bitwise_or(mask_blue, mask_purp))
    # dilate
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    ys, xs = np.where(mask > 0)
    if len(xs) < 100:
        # fallback center crop
        side = int(min(h, w) * 0.55)
        y0 = (h - side) // 2
        x0 = (w - side) // 2
        crop = img[y0 : y0 + side, x0 : x0 + side]
    else:
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        pad = 8
        crop = img[max(0, y0 - pad) : min(h, y1 + pad), max(0, x0 - pad) : min(w, x1 + pad)]
    side = min(crop.shape[0], crop.shape[1])
    crop = crop[:side, :side]
    return cv2.resize(crop, (512, 512), interpolation=cv2.INTER_AREA)


def main() -> None:
    path = ROOT / "assets" / "reference" / "roblox_light_dark_cherry.png"
    img = cv2.imread(str(path))
    assert img is not None, path
    warped = extract_board(img)
    cv2.imwrite(str(ROOT / "_debug_warped.png"), warped)
    print("warped", warped.shape, "mean", warped.mean())

    ori = BoardOrientation()
    tracker = AutoMoveTracker(orientation=ori, accept_score=8.0, confirm_hits=1)
    board = chess.Board()
    tracker.lock(warped)

    # Simulate e2e4: swap/clear cells using display coords
    after = warped.copy()
    cs = 64
    ec, er = ori.square_to_display("e2")
    fc, fr = ori.square_to_display("e4")
    print("e2 display", ec, er, "e4", fc, fr)
    # empty e2 using color from e3 empty-ish center board
    mc, mr = ori.square_to_display("e3")
    after[er * cs : (er + 1) * cs, ec * cs : (ec + 1) * cs] = warped[
        mr * cs : (mr + 1) * cs, mc * cs : (mc + 1) * cs
    ]
    after[fr * cs : (fr + 1) * cs, fc * cs : (fc + 1) * cs] = warped[
        er * cs : (er + 1) * cs, ec * cs : (ec + 1) * cs
    ]
    cv2.imwrite(str(ROOT / "_debug_after.png"), after)

    heat, pairs = tracker._square_deltas(tracker._ref_bgr, after)
    print("top changed:", pairs[:12])
    print("heat e2", heat[er, ec], "e4", heat[fr, fc], "mean", heat.mean())

    res = tracker.force_best(after, board)
    print("result", res.move, res.score if res.move else None, res.message)
    print("top", res.all_top[:8])

    # Same-frame sanity
    heat0, p0 = tracker._square_deltas(tracker._ref_bgr, warped)
    print("same-frame mean heat", float(heat0.mean()), "max", float(heat0.max()))


if __name__ == "__main__":
    main()
