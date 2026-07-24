"""PGN export and post-game review helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import chess
import chess.pgn

from chess_engine.stockfish_engine import StockfishEngine


@dataclass
class MoveReview:
    ply: int
    san: str
    uci: str
    played_eval: Optional[float]
    best_eval: Optional[float]
    loss_cp: Optional[float]
    classification: str  # best | excellent | good | inaccuracy | mistake | blunder
    best_move_san: str = ""


def board_to_pgn(
    board: chess.Board,
    white: str = "Light Cherry",
    black: str = "Dark Cherry",
    event: str = "Chess Vision Assistant",
) -> str:
    game = chess.pgn.Game()
    game.headers["Event"] = event
    game.headers["White"] = white
    game.headers["Black"] = black
    game.headers["Result"] = board.result(claim_draw=True) if board.is_game_over() else "*"
    node = game
    for move in board.move_stack:
        node = node.add_variation(move)
    exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
    return game.accept(exporter)


def pgn_from_uci_list(
    uci_moves: list[str],
    start_fen: str | None = None,
    white: str = "Light Cherry",
    black: str = "Dark Cherry",
) -> str:
    game = chess.pgn.Game()
    game.headers["Event"] = "Chess Vision Assistant"
    game.headers["White"] = white
    game.headers["Black"] = black
    if start_fen:
        board = chess.Board(start_fen)
        game.setup(board)
    else:
        board = chess.Board()
    node = game
    for uci in uci_moves:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            break
        node = node.add_variation(move)
        board.push(move)
    game.headers["Result"] = board.result(claim_draw=True) if board.is_game_over() else "*"
    exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
    return game.accept(exporter)


def classify_loss(loss_cp: float) -> str:
    loss = abs(loss_cp)
    if loss < 20:
        return "best"
    if loss < 50:
        return "excellent"
    if loss < 100:
        return "good"
    if loss < 150:
        return "inaccuracy"
    if loss < 300:
        return "mistake"
    return "blunder"


def _white_pov_pawns(eval_score) -> Optional[float]:
    if eval_score is None:
        return None
    return eval_score.as_pawns()


def review_game(
    engine: StockfishEngine,
    uci_moves: list[str],
    start_fen: str | None = None,
    movetime_ms: int = 200,
) -> list[MoveReview]:
    """Analyze each played move vs engine best (local Stockfish only)."""
    board = chess.Board(start_fen) if start_fen else chess.Board()
    reviews: list[MoveReview] = []

    for ply, uci in enumerate(uci_moves, start=1):
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            reviews.append(
                MoveReview(
                    ply=ply,
                    san=uci,
                    uci=uci,
                    played_eval=None,
                    best_eval=None,
                    loss_cp=None,
                    classification="illegal",
                )
            )
            break

        mover_is_white = board.turn == chess.WHITE
        san = board.san(move)

        before = engine.analyze(board.fen(), movetime_ms=movetime_ms, multipv=1, threads=2)
        best_eval = _white_pov_pawns(before.evaluation) if before.ok else None
        best_san = before.best_move_san if before.ok else ""

        board.push(move)
        after = engine.analyze(board.fen(), movetime_ms=movetime_ms, multipv=1, threads=2)
        after_wp = _white_pov_pawns(after.evaluation) if after.ok else None

        # Convert after-eval to pre-move side quality in white-POV terms:
        # for white mover, higher white-POV is better; played quality ≈ after_wp
        # for black mover, lower white-POV is better; played quality for black ≈ -after_wp
        played_eval = after_wp
        loss_cp = None
        cls = "unknown"
        if best_eval is not None and after_wp is not None:
            if mover_is_white:
                # best line would give ~best_eval (from multipv before); after move white POV
                # Use engine best move score from before as reference when available
                if before.lines and before.lines[0].score.as_pawns() is not None:
                    best_eval = before.lines[0].score.as_pawns()
                loss_cp = (best_eval - after_wp) * 100.0
            else:
                # black wants to minimize white-POV; best black move → lower after_wp
                if before.lines and before.lines[0].score.as_pawns() is not None:
                    best_eval = before.lines[0].score.as_pawns()
                loss_cp = (after_wp - best_eval) * 100.0
            cls = classify_loss(loss_cp)

        reviews.append(
            MoveReview(
                ply=ply,
                san=san,
                uci=uci,
                played_eval=played_eval,
                best_eval=best_eval,
                loss_cp=loss_cp,
                classification=cls,
                best_move_san=best_san,
            )
        )
    return reviews
