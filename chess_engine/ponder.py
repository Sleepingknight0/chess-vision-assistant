"""Bounded search + pondering — strong without pegging the machine.

Two ideas, like a real chess engine:

1. **Bounded think.** On your move the engine searches hard for a fixed budget
   (a few seconds / a depth cap) and then STOPS. It does not keep spinning at
   100% CPU forever, so the machine stays responsive.

2. **Ponder.** While it's the opponent's turn, the engine guesses their reply
   (the 2nd move of its best line) and thinks about the resulting position in
   advance. That warms the transposition table, so if the opponent plays the
   predicted move your next search is instantly deep. If the guess is wrong, the
   next search just starts fresh.

Threading contract: this thread is the ONLY place the persistent engine is
driven while analysing. GUI-thread callers that need the engine for something
else (changing the Stockfish path, quitting) must call `pause()` first.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import chess
import chess.engine
from PySide6.QtCore import QThread, Signal

from chess_engine.stockfish_engine import StockfishEngine, build_analysis_result

logger = logging.getLogger(__name__)

# Target tuple: (fen, multipv, threads, hash_mb, time_s, depth_cap)
Target = tuple


class ContinuousAnalyzer(QThread):
    updated = Signal(object)  # AnalysisResult (rebuilt as depth grows)
    depth_info = Signal(int, int)  # (current search depth, tbhits so far)

    def __init__(self, engine: StockfishEngine, parent=None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._cond = threading.Condition()
        self._target: Optional[Target] = None
        self._gen = 0
        self._running = True
        self._parked = threading.Event()
        self._last_cfg: Optional[tuple[int, int]] = None  # (threads, hash) applied

    # -- control (call from GUI thread) --------------------------------

    def analyze(
        self,
        fen: str,
        multipv: int,
        threads: int,
        hash_mb: int,
        time_s: float,
        depth: int,
    ) -> None:
        with self._cond:
            self._target = (
                fen,
                max(1, int(multipv)),
                int(threads),
                int(hash_mb),
                float(time_s),
                int(depth),
            )
            self._gen += 1
            self._parked.clear()
            self._cond.notify_all()

    def idle(self) -> None:
        with self._cond:
            self._target = None
            self._gen += 1
            self._cond.notify_all()

    def invalidate_config(self) -> None:
        """Force the next search to re-send engine options (Threads/Hash/Syzygy)."""
        with self._cond:
            self._last_cfg = None

    def pause(self, timeout: float = 3.0) -> None:
        """Stop analysing and block until the engine is free for other calls."""
        self.idle()
        self._parked.wait(timeout)

    def shutdown(self) -> None:
        with self._cond:
            self._running = False
            self._target = None
            self._gen += 1
            self._cond.notify_all()
        self.wait(3000)

    # -- worker --------------------------------------------------------

    def run(self) -> None:
        while True:
            with self._cond:
                while self._running and self._target is None:
                    self._parked.set()
                    self._cond.wait()
                if not self._running:
                    return
                target = self._target
                gen = self._gen
                self._parked.clear()
            try:
                self._stream(target, gen)
            except Exception as exc:  # noqa: BLE001
                logger.warning("analyzer error: %s", exc)
                try:
                    self._engine.close()
                except Exception:  # noqa: BLE001
                    pass
                self._last_cfg = None
                time.sleep(0.3)
            # Bounded search finished. If nobody queued a new position, park
            # (release the CPU) instead of looping the same search forever.
            with self._cond:
                if self._gen == gen:
                    self._target = None

    def _stream(self, target: Target, gen: int) -> None:
        fen, mpv, threads, hash_mb, time_s, depth = target
        try:
            board = chess.Board(fen)
        except ValueError:
            return
        if board.is_game_over():
            return

        # Configure only when thread/hash change — setting Hash clears the TT,
        # so reconfiguring every move would throw away the warm table.
        if self._last_cfg != (threads, hash_mb):
            self._engine.configure(threads=threads, skill_level=20, hash_mb=hash_mb)
            self._last_cfg = (threads, hash_mb)
        eng = self._engine._ensure()

        limit = chess.engine.Limit(time=max(0.05, time_s), depth=max(1, depth))
        latest: dict[int, dict] = {}
        last_emit = 0.0
        last_depth = -1
        with eng.analysis(board, limit, multipv=mpv) as analysis:
            for info in analysis:
                with self._cond:
                    if not self._running or self._gen != gen:
                        break
                mp = int(info.get("multipv", 1))
                if info.get("pv") and info.get("score") is not None:
                    latest[mp] = dict(info)
                d = info.get("depth")
                tbhits = int(info.get("tbhits", 0) or 0)
                now = time.monotonic()
                if latest and (d != last_depth or now - last_emit > 0.25):
                    result = build_analysis_result(board, latest.values(), fen)
                    if result.ok:
                        self.updated.emit(result)
                        if d is not None:
                            self.depth_info.emit(int(d), tbhits)
                        last_emit = now
                        last_depth = d if d is not None else last_depth
