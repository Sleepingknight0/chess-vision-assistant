"""Castling tests."""

import chess

from chess_core.special_moves import apply_and_fen, make_kingside_castle_white, make_queenside_castle_white


def test_kingside_castle():
    board, move = make_kingside_castle_white()
    assert board.is_castling(move)
    assert move in board.legal_moves
    fen = apply_and_fen(board, move)
    assert "K" in fen or board.piece_at(chess.G1)


def test_queenside_castle():
    board, move = make_queenside_castle_white()
    assert board.is_castling(move)
    assert move in board.legal_moves
    board.push(move)
    assert board.piece_at(chess.C1) == chess.Piece.from_symbol("K")
