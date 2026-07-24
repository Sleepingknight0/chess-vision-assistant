"""High-level move detection via pixel-diff AutoMoveTracker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import chess
import numpy as np

from board_detection.orientation import BoardOrientation
from move_detection.auto_tracker import AutoMoveTracker, AutoResult
from move_detection.diff_tracker import DiffTracker, MoveHypothesis


@dataclass
class DetectionEvent:
    kind: str  # move | watching | idle | error
    hypothesis: Optional[MoveHypothesis] = None
    message: str = ""
    debug: str = ""
    heat: Optional[np.ndarray] = None
    changed_squares: list | None = None


class MoveDetectionService:
    def __init__(self) -> None:
        self.auto = AutoMoveTracker(accept_score=10.0, confirm_hits=2)
        self.tracker = DiffTracker()  # legacy fallback unused in primary path
        self.enabled = True
        self.auto_recalibrate = False
        self._pending: Optional[MoveHypothesis] = None

    def configure(
        self,
        orientation: BoardOrientation,
        confidence_threshold: float = 0.42,
        debounce_ms: int = 320,
    ) -> None:
        self.auto.set_orientation(orientation)
        # Map UI 0.4-0.9 confidence-ish to pixel score threshold ~8-20
        # Pixel-diff scores: ~10+ is a clear move on Roblox boards
        self.auto.accept_score = 10.0
        # 2 consecutive settled frames must agree before auto-accept
        self.auto.confirm_hits = 2
        self.tracker.orientation = orientation

    def reset(self, board: chess.Board) -> None:
        self.auto.reset()
        self.tracker.reset()
        self.tracker.set_baseline_from_board(board)
        self._pending = None

    def set_reference_frame(
        self, warped: np.ndarray, board: chess.Board | None = None
    ) -> None:
        self.auto.lock(warped)
        if board is not None:
            try:
                self.tracker.lock_visual_reference(warped, board)
            except Exception:
                pass
        self._pending = None

    def on_frame(self, warped: np.ndarray, board: chess.Board) -> DetectionEvent:
        if not self.enabled:
            return DetectionEvent("idle", message="paused")
        result = self.auto.observe(warped, board)
        return self._from_auto(result)

    def scan_now(self, warped: np.ndarray, board: chess.Board) -> DetectionEvent:
        result = self.auto.force_best(warped, board)
        return self._from_auto(result, force=True)

    def _from_auto(self, result: AutoResult, force: bool = False) -> DetectionEvent:
        changed = result.changed_squares or []
        ch_txt = ",".join(f"{s}:{v:.0f}" for s, v in changed[:4])
        tops = " ".join(f"{u}:{s:.1f}" for s, u in (result.all_top or [])[:3])
        debug = f"{result.message}"
        if tops:
            debug += f" | {tops}"
        if ch_txt:
            debug += f" | Δsq[{ch_txt}]"

        if result.move is None:
            self._pending = None
            kind = "watching" if result.locked else "idle"
            return DetectionEvent(
                kind,
                message=result.message,
                debug=debug,
                heat=result.heat,
                changed_squares=changed,
            )

        moves = [result.move]
        for s, uci in (result.all_top or [])[1:5]:
            try:
                m = chess.Move.from_uci(uci)
                if m not in moves:
                    moves.append(m)
            except ValueError:
                pass

        # Normalize score ~0-1 for UI (pixel scores often 5-40)
        conf = min(1.0, float(result.score) / 30.0)
        hyp = MoveHypothesis(
            moves=moves,
            confidence=conf,
            emptied=[],
            filled=[],
            needs_user_choice=False,
            message=result.message,
        )
        self._pending = hyp

        if force or "ready to confirm" in result.message:
            return DetectionEvent(
                "move",
                hypothesis=hyp,
                message=result.message,
                debug=debug,
                heat=result.heat,
                changed_squares=changed,
            )

        # Watching candidate
        return DetectionEvent(
            "watching",
            hypothesis=hyp,
            message=result.message,
            debug=debug,
            heat=result.heat,
            changed_squares=changed,
        )

    @property
    def pending(self) -> Optional[MoveHypothesis]:
        return self._pending

    def clear_pending(self) -> None:
        self._pending = None

    def apply_accepted(
        self,
        board: chess.Board,
        warped: np.ndarray | None = None,
        *,
        warped_bgr: np.ndarray | None = None,
    ) -> None:
        img = warped if warped is not None else warped_bgr
        self.auto.on_move_applied(img)
        try:
            self.tracker.accept_move_applied(board, img)
        except Exception:
            pass
        self._pending = None
