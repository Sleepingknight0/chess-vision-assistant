"""FEN utility tests."""

import chess

from chess_core.board_state import BoardState
from chess_core.fen_utils import is_valid_fen, normalize_fen, starting_fen


def test_starting_fen_valid():
    assert is_valid_fen(starting_fen())


def test_invalid_fen():
    assert not is_valid_fen("not a fen")
    assert not is_valid_fen("")


def test_normalize():
    fen = normalize_fen(starting_fen())
    assert fen.split()[0] == chess.STARTING_BOARD_FEN


def test_board_state_roundtrip():
    bs = BoardState.standard()
    fen = bs.fen()
    bs2 = BoardState.from_fen(fen)
    assert bs2.fen().split()[0] == fen.split()[0]


def test_set_fen():
    bs = BoardState.standard()
    empty = "8/8/8/8/8/8/8/4K2k w - - 0 1"
    bs.set_fen(empty)
    assert bs.piece_at("e1") == "K"
