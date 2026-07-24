"""En passant tests."""

import chess

from chess_core.special_moves import make_en_passant
from chess_core.move_validate import is_en_passant


def test_en_passant_legal():
    board, move = make_en_passant()
    assert is_en_passant(move, board)
    assert move in board.legal_moves
    board.push(move)
    assert board.piece_at(chess.D6) == chess.Piece.from_symbol("P")
    assert board.piece_at(chess.D5) is None
