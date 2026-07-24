"""Board state wrapper around python-chess."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import chess

from chess_core.fen_utils import STARTING_FEN


@dataclass
class BoardState:
    """Mutable game state with undo stack for detection corrections."""

    board: chess.Board = field(default_factory=chess.Board)
    history_uci: list[str] = field(default_factory=list)
    _snapshots: list[str] = field(default_factory=list, repr=False)

    @classmethod
    def from_fen(cls, fen: str) -> BoardState:
        return cls(board=chess.Board(fen))

    @classmethod
    def standard(cls) -> BoardState:
        return cls(board=chess.Board(STARTING_FEN))

    def fen(self) -> str:
        return self.board.fen()

    def reset_standard(self) -> None:
        self.board.reset()
        self.history_uci.clear()
        self._snapshots.clear()

    def set_fen(self, fen: str) -> None:
        self.board.set_fen(fen)
        self.history_uci.clear()
        self._snapshots.clear()

    def side_to_move_is_white(self) -> bool:
        return self.board.turn == chess.WHITE

    def is_user_turn(self, user_is_white: bool) -> bool:
        return self.side_to_move_is_white() == user_is_white

    def push_uci(self, uci: str) -> chess.Move:
        move = chess.Move.from_uci(uci)
        if move not in self.board.legal_moves:
            raise ValueError(f"Illegal move: {uci}")
        self._snapshots.append(self.board.fen())
        self.board.push(move)
        self.history_uci.append(uci)
        return move

    def push_move(self, move: chess.Move) -> None:
        if move not in self.board.legal_moves:
            raise ValueError(f"Illegal move: {move.uci()}")
        self._snapshots.append(self.board.fen())
        self.board.push(move)
        self.history_uci.append(move.uci())

    def undo_last(self) -> bool:
        if not self._snapshots:
            if self.board.move_stack:
                self.board.pop()
                if self.history_uci:
                    self.history_uci.pop()
                return True
            return False
        fen = self._snapshots.pop()
        self.board.set_fen(fen)
        if self.history_uci:
            self.history_uci.pop()
        return True

    def legal_uci(self) -> list[str]:
        return [m.uci() for m in self.board.legal_moves]

    def san_history(self) -> list[str]:
        """Rebuild SAN list from UCI history on a fresh board of same start.

        Phase 1: approximate via replaying from start only when board was
        standard-started; otherwise return UCI.
        """
        temp = chess.Board()
        sans: list[str] = []
        # Replay only if current position matches after full history from start
        try:
            for uci in self.history_uci:
                move = chess.Move.from_uci(uci)
                sans.append(temp.san(move))
                temp.push(move)
            if temp.fen().split()[0] == self.board.fen().split()[0]:
                return sans
        except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError):
            pass
        return list(self.history_uci)

    def piece_at(self, square_name: str) -> Optional[str]:
        sq = chess.parse_square(square_name)
        piece = self.board.piece_at(sq)
        return piece.symbol() if piece else None

    def set_piece(self, square_name: str, symbol: Optional[str]) -> None:
        sq = chess.parse_square(square_name)
        if symbol is None or symbol == "":
            self.board.remove_piece_at(sq)
        else:
            self.board.set_piece_at(sq, chess.Piece.from_symbol(symbol))

    def copy(self) -> BoardState:
        return BoardState(
            board=self.board.copy(stack=True),
            history_uci=list(self.history_uci),
            _snapshots=list(self._snapshots),
        )
