"""Candidate legal moves from occupancy emptied/filled squares."""

from __future__ import annotations

import chess


def candidates_from_squares(
    board: chess.Board, emptied: list[str], filled: list[str]
) -> list[chess.Move]:
    """Return legal moves consistent with emptied/filled algebraic squares."""
    empty_set = {s.lower() for s in emptied}
    fill_set = {s.lower() for s in filled}
    if not empty_set and not fill_set:
        return []

    results: list[chess.Move] = []
    for move in board.legal_moves:
        fr = chess.square_name(move.from_square)
        to = chess.square_name(move.to_square)

        if board.is_castling(move):
            # King moves two squares; rook also moves
            rook_from, rook_to = _castle_rook_squares(move)
            expected_empty = {fr, rook_from}
            expected_fill = {to, rook_to}
            # Captures of intermediate not relevant; tolerate subset matches
            if fr in empty_set and to in fill_set:
                results.append(move)
            elif empty_set == expected_empty and fill_set == expected_fill:
                results.append(move)
            elif empty_set.issubset(expected_empty | expected_fill) and to in fill_set:
                results.append(move)
            continue

        if board.is_en_passant(move):
            if board.turn == chess.WHITE:
                cap_sq = chess.square_name(move.to_square - 8)
            else:
                cap_sq = chess.square_name(move.to_square + 8)
            if fr in empty_set and to in fill_set:
                results.append(move)
            elif fr in empty_set and cap_sq in empty_set and to in fill_set:
                results.append(move)
            continue

        if board.is_capture(move):
            # from emptied, to stays occupied (or may flicker)
            if fr in empty_set and (to in fill_set or to not in empty_set):
                if len(empty_set) <= 2 and (not fill_set or to in fill_set):
                    results.append(move)
            continue

        # Quiet move
        if fr in empty_set and to in fill_set:
            if len(empty_set) == 1 and len(fill_set) == 1:
                results.append(move)
            elif len(empty_set) <= 2 and len(fill_set) <= 2:
                # animation ghost tolerance
                results.append(move)

    # Deduplicate
    seen: set[str] = set()
    uniq: list[chess.Move] = []
    for m in results:
        u = m.uci()
        if u not in seen:
            seen.add(u)
            uniq.append(m)
    return uniq


def _castle_rook_squares(move: chess.Move) -> tuple[str, str]:
    if move.to_square > move.from_square:  # kingside
        if chess.square_rank(move.from_square) == 0:
            return "h1", "f1"
        return "h8", "f8"
    if chess.square_rank(move.from_square) == 0:
        return "a1", "d1"
    return "a8", "d8"


def score_candidate(
    board: chess.Board,
    move: chess.Move,
    emptied: list[str],
    filled: list[str],
) -> float:
    """Heuristic confidence 0..1 for a candidate given observed squares."""
    empty_set = {s.lower() for s in emptied}
    fill_set = {s.lower() for s in filled}
    fr = chess.square_name(move.from_square)
    to = chess.square_name(move.to_square)
    score = 0.5
    if fr in empty_set:
        score += 0.25
    if to in fill_set:
        score += 0.25
    if board.is_capture(move) and to not in empty_set:
        score += 0.05
    if board.is_castling(move):
        rook_from, rook_to = _castle_rook_squares(move)
        if rook_from in empty_set:
            score += 0.1
        if rook_to in fill_set:
            score += 0.1
    # penalize extra noise
    extra = (empty_set | fill_set) - {fr, to}
    score -= 0.05 * len(extra)
    return max(0.0, min(1.0, score))
