"""Track visual score deltas and emit move hypotheses when stable."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import chess
import numpy as np

from board_detection.orientation import BoardOrientation
from move_detection.candidates import candidates_from_squares, score_candidate
from vision.occupancy import OccupancyDetector
from vision.stability import StabilityGate


@dataclass
class MoveHypothesis:
    moves: list[chess.Move]
    confidence: float
    emptied: list[str]
    filled: list[str]
    needs_promotion_choice: bool = False
    needs_user_choice: bool = False
    message: str = ""


@dataclass
class DiffTracker:
    orientation: BoardOrientation = field(default_factory=BoardOrientation)
    detector: OccupancyDetector = field(
        default_factory=lambda: OccupancyDetector(delta_threshold=0.06)
    )
    stability: StabilityGate = field(
        default_factory=lambda: StabilityGate(debounce_ms=320, motion_threshold=2.5)
    )
    confidence_threshold: float = 0.42  # auto-accept threshold (visual)
    delta_threshold: float = 0.06
    min_global_delta: float = 0.28  # total abs change to consider a move happened
    _ref_scores: Optional[list[list[float]]] = None
    _locked_board_fen: str = ""
    _armed: bool = False
    _force_scan: bool = False
    _cooldown_until: float = 0.0
    _frames_since_lock: int = 0

    def reset(self) -> None:
        self._ref_scores = None
        self._locked_board_fen = ""
        self._armed = False
        self._force_scan = False
        self._cooldown_until = 0.0
        self._frames_since_lock = 0
        self.detector.reset_baseline()
        self.stability.reset()

    def set_baseline_from_board(self, board: chess.Board) -> None:
        self._locked_board_fen = board.fen()
        self._armed = True
        self.stability.reset()

    def lock_visual_reference(self, warped_bgr, board: chess.Board) -> None:
        scores = self.detector.score_frame(warped_bgr, self.orientation)
        self._ref_scores = scores
        self.detector.set_reference_scores(scores)
        self._locked_board_fen = board.fen()
        self._armed = True
        self._frames_since_lock = 0
        self.stability.reset()
        import time

        # Brief cooldown so animation after our update doesn't re-trigger
        self._cooldown_until = time.monotonic() + 0.45

    def request_force_scan(self) -> None:
        self._force_scan = True

    def process_frame(self, warped_bgr, board: chess.Board) -> Optional[MoveHypothesis]:
        import time

        if not self._armed:
            self.set_baseline_from_board(board)

        now = time.monotonic()
        if now < self._cooldown_until:
            # Keep updating gray ref so we don't see stale motion later
            self.stability.update(warped_bgr)
            return None

        stable, motion = self.stability.update(warped_bgr)
        scores = self.detector.score_frame(warped_bgr, self.orientation)
        self._frames_since_lock += 1

        # First visual lock
        if self._ref_scores is None:
            if stable or self._force_scan:
                self._ref_scores = [r[:] for r in scores]
                self.detector.set_reference_scores(scores)
                self._force_scan = False
                self._frames_since_lock = 0
            return None

        force = self._force_scan
        if force:
            self._force_scan = False
        else:
            if not stable:
                return None
            pending = self.stability.consume_pending()
            total = self._total_abs_delta(self._ref_scores, scores)
            # Trigger if: motion settled OR clear global visual change
            if not pending and total < self.min_global_delta:
                return None
            # Ignore tiny jitter right after lock
            if self._frames_since_lock < 4 and total < self.min_global_delta * 1.5:
                return None

        hyp = self._hypothesize(board, self._ref_scores, scores)
        return hyp

    def scan_now(self, warped_bgr, board: chess.Board) -> MoveHypothesis:
        if self._ref_scores is None:
            scores = self.detector.score_frame(warped_bgr, self.orientation)
            self._ref_scores = [r[:] for r in scores]
            return MoveHypothesis(
                moves=[],
                confidence=0.0,
                emptied=[],
                filled=[],
                message="reference frame locked — waiting for a move in game",
            )
        scores = self.detector.score_frame(warped_bgr, self.orientation)
        hyp = self._hypothesize(board, self._ref_scores, scores)
        if hyp is None:
            return MoveHypothesis(
                moves=[],
                confidence=0.0,
                emptied=[],
                filled=[],
                message="no change detected yet",
            )
        return hyp

    def _hypothesize(
        self,
        board: chess.Board,
        before_scores: list[list[float]],
        after_scores: list[list[float]],
    ) -> Optional[MoveHypothesis]:
        decreased, increased, deltas = self.detector.delta_map(
            before_scores, after_scores, delta_threshold=self.delta_threshold
        )

        emptied_vis = [self.orientation.display_to_square(c, r) for c, r in decreased]
        filled_vis = [self.orientation.display_to_square(c, r) for c, r in increased]

        emptied = [sq for sq in emptied_vis if board.piece_at(chess.parse_square(sq))]
        if not emptied and decreased:
            ranked_dec = sorted(decreased, key=lambda cr: deltas[cr[1]][cr[0]])
            for c, r in ranked_dec[:5]:
                sq = self.orientation.display_to_square(c, r)
                if board.piece_at(chess.parse_square(sq)):
                    emptied.append(sq)

        filled: list[str] = []
        for sq in filled_vis:
            piece = board.piece_at(chess.parse_square(sq))
            if piece is None or piece.color != board.turn:
                filled.append(sq)
        if not filled and increased:
            ranked_inc = sorted(increased, key=lambda cr: -deltas[cr[1]][cr[0]])
            for c, r in ranked_inc[:5]:
                sq = self.orientation.display_to_square(c, r)
                piece = board.piece_at(chess.parse_square(sq))
                if piece is None or piece.color != board.turn:
                    filled.append(sq)

        emptied2, filled2 = self._infer_from_board_deltas(board, deltas)
        if not emptied:
            emptied = emptied2
        if not filled:
            filled = filled2

        total = self._total_abs_delta(before_scores, after_scores)
        if total < self.min_global_delta * 0.7 and not emptied:
            return None

        moves = candidates_from_squares(board, emptied, filled)

        if not moves and emptied:
            for sq in emptied:
                from_sq = chess.parse_square(sq)
                for m in board.legal_moves:
                    if m.from_square == from_sq:
                        if not filled or chess.square_name(m.to_square) in filled:
                            moves.append(m)
            seen: set[str] = set()
            uniq: list[chess.Move] = []
            for m in moves:
                if m.uci() not in seen:
                    seen.add(m.uci())
                    uniq.append(m)
            moves = uniq

        if not moves:
            moves = self._rank_legal_by_delta(board, deltas)

        if not moves:
            if total >= self.min_global_delta:
                # Something changed but no legal match — rank all legal by delta
                moves = self._rank_legal_by_delta(board, deltas, min_score=0.03)
            if not moves:
                return None

        rescored: list[tuple[float, chess.Move]] = []
        for m in moves:
            base = score_candidate(board, m, emptied, filled)
            fr = chess.square_name(m.from_square)
            to = chess.square_name(m.to_square)
            fc, fr_ = self.orientation.square_to_display(fr)
            tc, tr = self.orientation.square_to_display(to)
            drop = max(0.0, -deltas[fr_][fc])
            rise = max(0.0, deltas[tr][tc])
            vis = max(0.0, min(1.0, (drop + rise) / 0.35))
            # Quiet moves often have weaker fill signal
            if not board.is_capture(m):
                vis = max(vis, drop / 0.25 * 0.7)
            score = 0.35 * base + 0.65 * vis
            rescored.append((score, m))
        rescored.sort(key=lambda x: -x[0])
        best_conf = float(rescored[0][0])
        ranked = [m for _, m in rescored]

        # Promotion: auto-prefer queen unless user disabled
        promo_groups: dict[str, list[chess.Move]] = {}
        for m in ranked:
            if m.promotion:
                promo_groups.setdefault(m.uci()[:4], []).append(m)
        if promo_groups:
            # Replace multi-promo with queen-only for auto, keep all if ambiguous bases
            auto_ranked: list[chess.Move] = []
            for m in ranked:
                if not m.promotion:
                    auto_ranked.append(m)
                elif m.promotion == chess.QUEEN:
                    auto_ranked.append(m)
            if auto_ranked:
                ranked = auto_ranked
                rescored = [(s, m) for s, m in rescored if m in ranked or m.promotion == chess.QUEEN]
                if rescored:
                    best_conf = float(rescored[0][0])

        gap = 1.0
        if len(rescored) > 1:
            gap = rescored[0][0] - rescored[1][0]

        # Auto-friendly: single clear candidate or large gap
        needs_choice = False
        if len(ranked) > 1 and gap < 0.08 and best_conf < 0.70:
            needs_choice = True
        if best_conf < self.confidence_threshold * 0.75:
            needs_choice = True

        msg = f"auto {ranked[0].uci()} conf={best_conf:.0%}"
        return MoveHypothesis(
            moves=ranked,
            confidence=best_conf,
            emptied=emptied,
            filled=filled,
            needs_user_choice=needs_choice,
            needs_promotion_choice=False,
            message=msg,
        )

    def _infer_from_board_deltas(
        self, board: chess.Board, deltas: list[list[float]]
    ) -> tuple[list[str], list[str]]:
        drops: list[tuple[float, str]] = []
        rises: list[tuple[float, str]] = []
        for sq in chess.SQUARES:
            name = chess.square_name(sq)
            col, row = self.orientation.square_to_display(name)
            d = deltas[row][col]
            piece = board.piece_at(sq)
            if piece is not None and piece.color == board.turn and d < -0.035:
                drops.append((d, name))
            if (piece is None or piece.color != board.turn) and d > 0.035:
                rises.append((d, name))
        drops.sort()
        rises.sort(reverse=True)
        return [n for _, n in drops[:4]], [n for _, n in rises[:4]]

    def _rank_legal_by_delta(
        self, board: chess.Board, deltas: list[list[float]], min_score: float = 0.05
    ) -> list[chess.Move]:
        ranked: list[tuple[float, chess.Move]] = []
        for m in board.legal_moves:
            fr = chess.square_name(m.from_square)
            to = chess.square_name(m.to_square)
            fc, fr_ = self.orientation.square_to_display(fr)
            tc, tr = self.orientation.square_to_display(to)
            score = (-deltas[fr_][fc]) + max(0.0, deltas[tr][tc])
            if board.is_capture(m):
                score += 0.02
            ranked.append((score, m))
        ranked.sort(key=lambda x: -x[0])
        return [m for s, m in ranked if s > min_score][:10]

    @staticmethod
    def _total_abs_delta(a: list[list[float]], b: list[list[float]]) -> float:
        total = 0.0
        for r in range(8):
            for c in range(8):
                total += abs(b[r][c] - a[r][c])
        return total

    def accept_move_applied(self, board: chess.Board, warped_bgr=None) -> None:
        self._locked_board_fen = board.fen()
        self.stability.reset()
        if warped_bgr is not None:
            self.lock_visual_reference(warped_bgr, board)
        else:
            self._ref_scores = None
