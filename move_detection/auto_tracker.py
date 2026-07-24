"""Vision + chess-logic move tracker.

Vision only answers: which squares changed, and how much.
Chess logic answers: given the board, which legal moves explain that.

UI should prefer explicit Before→After scan over continuous guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import chess
import cv2
import numpy as np

from board_detection.orientation import BoardOrientation
from move_detection.chess_move_finder import explain_pattern, find_moves
from vision.grid import BoardGrid


@dataclass
class AutoResult:
    move: Optional[chess.Move]
    score: float
    all_top: list[tuple[float, str]]
    locked: bool
    message: str = ""
    heat: Optional[np.ndarray] = None
    changed_squares: list[tuple[str, float]] | None = None


class AutoMoveTracker:
    def __init__(
        self,
        orientation: BoardOrientation | None = None,
        accept_score: float = 12.0,
        confirm_hits: int = 2,
    ) -> None:
        self.orientation = orientation or BoardOrientation()
        self.accept_score = accept_score
        self.confirm_hits = max(1, confirm_hits)
        self._ref_bgr: Optional[np.ndarray] = None
        self._hits_uci = ""
        self._hits = 0
        self._cooldown = 0
        self._last_heat: Optional[np.ndarray] = None

    def reset(self) -> None:
        self._ref_bgr = None
        self._hits_uci = ""
        self._hits = 0
        self._cooldown = 0
        self._last_heat = None

    def set_orientation(self, orientation: BoardOrientation) -> None:
        self.orientation = orientation

    @property
    def locked(self) -> bool:
        return self._ref_bgr is not None

    @property
    def last_heat(self) -> Optional[np.ndarray]:
        return self._last_heat

    def lock(self, warped_bgr: np.ndarray) -> None:
        self._ref_bgr = self._prep(warped_bgr)
        self._hits_uci = ""
        self._hits = 0
        self._cooldown = 2
        self._last_heat = np.zeros((8, 8), dtype=np.float32)

    def observe(self, warped_bgr: np.ndarray, board: chess.Board) -> AutoResult:
        """Continuous watch — stricter than force_best (needs consecutive hits)."""
        if self._cooldown > 0:
            self._cooldown -= 1
            if not self.locked:
                self.lock(warped_bgr)
            return AutoResult(None, 0.0, [], self.locked, f"cooldown {self._cooldown}", self._last_heat, [])

        if not self.locked:
            self.lock(warped_bgr)
            return AutoResult(None, 0.0, [], True, "pre-move frame locked", self._last_heat, [])

        prev_heat = self._last_heat
        res = self._analyze(warped_bgr, board)
        if res.move is None:
            self._hits = 0
            self._hits_uci = ""
            return res

        # Settle gate: the heat map must freeze between consecutive frames
        # before any confirmation — otherwise a mid-animation frame (piece
        # still sliding across the board) can be accepted as the final move.
        heat_stable = (
            prev_heat is not None
            and res.heat is not None
            and float(np.max(np.abs(res.heat - prev_heat))) < 2.5
        )
        if not heat_stable:
            res.message = f"waiting for piece to settle | {res.message}"
            return res

        # consecutive confirmation for auto mode
        uci = res.move.uci()
        if uci == self._hits_uci:
            self._hits += 1
        else:
            self._hits_uci = uci
            self._hits = 1

        if res.score >= self.accept_score and self._hits >= self.confirm_hits:
            self._hits = 0
            self._hits_uci = ""
            res.message = f"ready to confirm {res.message}"
            return res

        if res.score >= self.accept_score * 1.5 and self._hits >= 1:
            self._hits = 0
            self._hits_uci = ""
            res.message = f"ready to confirm {res.message}"
            return res

        res.move = res.move  # keep candidate
        res.message = f"waiting conf {uci} ({self._hits}/{self.confirm_hits}) | {res.message}"
        # Downgrade so service treats as watching unless message has ready to confirm
        return res

    def force_best(self, warped_bgr: np.ndarray, board: chess.Board) -> AutoResult:
        """One-shot Before/After compare — primary reliable path."""
        if not self.locked:
            self.lock(warped_bgr)
            return AutoResult(
                None, 0.0, [], True,
                "pre-move frame saved → move in game → press capture move again",
                None, [],
            )
        return self._analyze(warped_bgr, board)

    def on_move_applied(self, warped_bgr: np.ndarray | None) -> None:
        self._hits = 0
        self._hits_uci = ""
        if warped_bgr is not None:
            self.lock(warped_bgr)
            self._cooldown = 4
        else:
            self._ref_bgr = None

    def _analyze(self, warped_bgr: np.ndarray, board: chess.Board) -> AutoResult:
        cur = self._prep(warped_bgr)
        heat, pairs = self._square_deltas(self._ref_bgr, cur)
        self._last_heat = heat
        max_d = float(np.max(heat)) if heat.size else 0.0

        if max_d < 4.0:
            return AutoResult(
                None, 0.0, [], True,
                f"image unchanged maxΔ={max_d:.0f} — no move detected yet",
                heat, pairs[:6],
            )

        left_scores, arrive_scores = self._stm_leave_arrive(board, heat)
        pattern = explain_pattern(board, left_scores, arrive_scores)

        cands = find_moves(
            board,
            left_scores=left_scores,
            arrive_scores=arrive_scores,
            leave_min=7.0,
            arrive_min=5.0,
        )
        # Relax once if empty
        if not cands:
            cands = find_moves(
                board,
                left_scores=left_scores,
                arrive_scores=arrive_scores,
                leave_min=4.5,
                arrive_min=3.0,
            )

        if not cands:
            return AutoResult(
                None, 0.0, [], True,
                f"{pattern} | no legal move explains the change",
                heat, pairs[:8],
            )

        top_list = [(c.score, c.move.uci()) for c in cands[:8]]
        best = cands[0]
        fr = chess.square_name(best.move.from_square)
        to = chess.square_name(best.move.to_square)
        piece = board.piece_at(best.move.from_square)
        sym = piece.symbol() if piece else "?"
        msg = f"{sym} {fr}→{to} ({best.move.uci()})={best.score:.0f} | {best.reason} | {pattern}"

        return AutoResult(
            move=best.move,
            score=best.score,
            all_top=top_list,
            locked=True,
            message=msg,
            heat=heat,
            changed_squares=pairs[:8],
        )

    def _stm_leave_arrive(
        self, board: chess.Board, heat: np.ndarray
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Map heat into leave scores (STM pieces) and arrive scores (empty/enemy)."""
        left: dict[str, float] = {}
        arrive: dict[str, float] = {}
        for sq in chess.SQUARES:
            name = chess.square_name(sq)
            col, row = self.orientation.square_to_display(name)
            d = float(heat[row, col])
            piece = board.piece_at(sq)
            if piece is not None and piece.color == board.turn:
                left[name] = d
            else:
                # empty or opponent: arrival / capture target
                arrive[name] = d
        return left, arrive

    def _prep(self, warped_bgr: np.ndarray) -> np.ndarray:
        h, w = warped_bgr.shape[:2]
        size = min(h, w)
        img = warped_bgr[:size, :size]
        if size != 512:
            img = cv2.resize(img, (512, 512), interpolation=cv2.INTER_AREA)
        return img.copy()

    def _square_deltas(
        self, ref_bgr: np.ndarray, cur_bgr: np.ndarray
    ) -> tuple[np.ndarray, list[tuple[str, float]]]:
        size = ref_bgr.shape[0]
        grid = BoardGrid(size=size, orientation=self.orientation)
        heat = np.zeros((8, 8), dtype=np.float32)
        pairs: list[tuple[str, float]] = []
        ref_g = cv2.cvtColor(ref_bgr, cv2.COLOR_BGR2GRAY)
        cur_g = cv2.cvtColor(cur_bgr, cv2.COLOR_BGR2GRAY)

        for row in range(8):
            for col in range(8):
                x0, y0, x1, y1 = grid.cell_rect_display(col, row)
                cw, ch = x1 - x0, y1 - y0
                mx, my = int(cw * 0.18), int(ch * 0.18)
                a = ref_bgr[y0 + my : y1 - my, x0 + mx : x1 - mx]
                b = cur_bgr[y0 + my : y1 - my, x0 + mx : x1 - mx]
                ga = ref_g[y0 + my : y1 - my, x0 + mx : x1 - mx]
                gb = cur_g[y0 + my : y1 - my, x0 + mx : x1 - mx]
                if a.size == 0 or b.size == 0:
                    continue
                d_color = float(np.mean(cv2.absdiff(a, b)))
                d_gray = float(np.mean(cv2.absdiff(ga, gb)))
                ea = cv2.Canny(ga, 30, 100)
                eb = cv2.Canny(gb, 30, 100)
                d_edge = float(np.mean(cv2.absdiff(ea, eb)))
                d_std = abs(float(np.std(gb.astype(np.float32)) - np.std(ga.astype(np.float32))))
                score = 0.45 * d_color + 0.25 * d_gray + 0.15 * d_edge + 0.15 * d_std
                heat[row, col] = score
                pairs.append((self.orientation.display_to_square(col, row), score))
        pairs.sort(key=lambda x: -x[1])
        return heat, pairs
