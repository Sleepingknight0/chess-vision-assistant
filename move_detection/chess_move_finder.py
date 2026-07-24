"""Chess-logic-first move finder from visual square changes.

Given which squares "lost a piece" and which "gained a piece" (from vision),
return only legal moves that explain the change. Ranking uses visual scores.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess


@dataclass
class MoveCandidate:
    move: chess.Move
    score: float
    reason: str


def find_moves(
    board: chess.Board,
    *,
    left_scores: dict[str, float],
    arrive_scores: dict[str, float],
    leave_min: float = 6.0,
    arrive_min: float = 4.0,
) -> list[MoveCandidate]:
    """Find legal moves explaining left/arrive visual evidence.

    left_scores: square -> how strongly a side-to-move piece appears to have left
    arrive_scores: square -> how strongly something appears to have arrived
    """
    # Origins: STM pieces with strong leave signal
    origins = [
        sq
        for sq, sc in sorted(left_scores.items(), key=lambda x: -x[1])
        if sc >= leave_min
        and board.piece_at(chess.parse_square(sq)) is not None
        and board.piece_at(chess.parse_square(sq)).color == board.turn
    ]
    # If vision missed leave, use any STM piece square with any positive leave score
    if not origins:
        origins = [
            sq
            for sq, sc in sorted(left_scores.items(), key=lambda x: -x[1])
            if sc >= leave_min * 0.5
            and board.piece_at(chess.parse_square(sq)) is not None
            and board.piece_at(chess.parse_square(sq)).color == board.turn
        ][:4]

    dests = [
        sq
        for sq, sc in sorted(arrive_scores.items(), key=lambda x: -x[1])
        if sc >= arrive_min
    ]

    results: list[MoveCandidate] = []
    seen: set[str] = set()

    def add(move: chess.Move, score: float, reason: str) -> None:
        u = move.uci()
        if u in seen:
            return
        if move not in board.legal_moves:
            return
        seen.add(u)
        results.append(MoveCandidate(move=move, score=score, reason=reason))

    # --- Path A: classic from left → to arrive ---
    if origins and dests:
        for fr in origins:
            for to in dests:
                for move in _moves_between(board, fr, to):
                    sc = left_scores.get(fr, 0) * 0.65 + arrive_scores.get(to, 0) * 0.35
                    add(move, sc, f"หาย={fr} มา={to}")

    # --- Path B: only know origin → any legal destination, rank by arrive score ---
    if origins:
        for fr in origins:
            fr_sc = left_scores.get(fr, 0.0)
            for move in board.legal_moves:
                if chess.square_name(move.from_square) != fr:
                    continue
                to = chess.square_name(move.to_square)
                to_sc = arrive_scores.get(to, 0.0)
                # Destination must show *some* change — a piece arriving is
                # always visible. Without this, a cursor hovering the origin
                # square invents quiet moves to untouched squares.
                if (
                    to_sc < arrive_min * 0.4
                    and not board.is_capture(move)
                    and not board.is_castling(move)
                ):
                    continue
                sc = fr_sc * 0.7 + to_sc * 0.3
                add(move, sc, f"ออกจาก={fr} ไป={to} (legal)")

    # --- Path C: only know destination → legal movers into that square ---
    if dests and not results:
        for to in dests[:3]:
            for move in board.legal_moves:
                if chess.square_name(move.to_square) != to:
                    continue
                fr = chess.square_name(move.from_square)
                sc = left_scores.get(fr, 0) * 0.5 + arrive_scores.get(to, 0) * 0.5
                add(move, sc, f"เข้า={to} จาก={fr}")

    # --- Castling special: king left two squares + rook pattern ---
    for move in board.legal_moves:
        if not board.is_castling(move):
            continue
        fr = chess.square_name(move.from_square)
        to = chess.square_name(move.to_square)
        if left_scores.get(fr, 0) >= leave_min * 0.6:
            sc = left_scores.get(fr, 0) + arrive_scores.get(to, 0)
            add(move, sc, "โรเคด")

    results.sort(key=lambda c: -c.score)
    return results


def _moves_between(board: chess.Board, fr: str, to: str) -> list[chess.Move]:
    """Legal moves from fr to to (including promotions)."""
    out: list[chess.Move] = []
    f = chess.parse_square(fr)
    t = chess.parse_square(to)
    for move in board.legal_moves:
        if move.from_square == f and move.to_square == t:
            out.append(move)
    # Prefer queen promotion first
    out.sort(key=lambda m: (0 if m.promotion == chess.QUEEN else 1 if m.promotion else 2))
    return out


def explain_pattern(
    board: chess.Board,
    left_scores: dict[str, float],
    arrive_scores: dict[str, float],
) -> str:
    left = [f"{s}:{v:.0f}" for s, v in sorted(left_scores.items(), key=lambda x: -x[1])[:3] if v >= 4]
    arr = [f"{s}:{v:.0f}" for s, v in sorted(arrive_scores.items(), key=lambda x: -x[1])[:3] if v >= 4]
    stm = "White" if board.turn == chess.WHITE else "Black"
    return f"ตา{stm} | หมากออก[{','.join(left) or '-'}] | หมากเข้า[{','.join(arr) or '-'}]"
