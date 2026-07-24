"""Helpers for castling, en passant, and promotion (test-friendly)."""

from __future__ import annotations

import chess


def make_kingside_castle_white() -> tuple[chess.Board, chess.Move]:
    board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQK2R w KQkq - 0 1")
    # Clear path: remove bishop and knight already absent in this FEN? Need clear f1 g1
    board = chess.Board("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
    move = chess.Move.from_uci("e1g1")
    return board, move


def make_queenside_castle_white() -> tuple[chess.Board, chess.Move]:
    board = chess.Board("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
    move = chess.Move.from_uci("e1c1")
    return board, move


def make_en_passant() -> tuple[chess.Board, chess.Move]:
    # After black plays d7-d5 as double push while white pawn on e5
    board = chess.Board("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3")
    move = chess.Move.from_uci("e5d6")
    return board, move


def make_promotion() -> tuple[chess.Board, chess.Move]:
    board = chess.Board("8/P7/8/8/8/8/8/4K2k w - - 0 1")
    move = chess.Move.from_uci("a7a8q")
    return board, move


def apply_and_fen(board: chess.Board, move: chess.Move) -> str:
    if move not in board.legal_moves:
        raise ValueError(f"Illegal: {move.uci()}")
    board.push(move)
    return board.fen()
