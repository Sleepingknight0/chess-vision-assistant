"""Background Stockfish analysis — never block the UI thread."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QThread, Signal

from chess_engine.stockfish_engine import PRESETS

if TYPE_CHECKING:
    from gui.app_state import AppState


class AnalyzeWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        state: "AppState",
        *,
        fen: str | None = None,
        movetime_ms: int | None = None,
        multipv: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.fen = fen
        self.movetime_ms = movetime_ms
        self.multipv = multipv

    def run(self) -> None:
        try:
            eng = self.state.profile.engine
            preset = PRESETS.get(eng.preset, PRESETS["balanced"])
            # Cap time so UI never feels dead — deep preset still limited for live
            movetime = self.movetime_ms
            if movetime is None:
                movetime = min(int(eng.movetime_ms or preset["movetime_ms"]), 1200)
            multipv = self.multipv if self.multipv is not None else min(eng.multipv, 3)
            threads = max(1, min(int(eng.threads or 2), 4))
            fen = self.fen or self.state.board_state.fen()
            result = self.state.engine.analyze(
                fen,
                movetime_ms=movetime,
                multipv=multipv,
                threads=threads,
                skill_level=eng.skill_level,
            )
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class GrokWorker(QThread):
    """Ask Grok (xAI) about a position without blocking the UI."""

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, state: "AppState", *, fen: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.fen = fen

    def run(self) -> None:
        try:
            fen = self.fen or self.state.board_state.fen()
            # Ground Grok with the latest Stockfish lines when they match this position
            hint = self.state.last_analysis
            if hint is not None and (hint.fen != fen or not hint.ok):
                hint = None
            result = self.state.grok.analyze(fen, hint=hint)
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class GrokValidateWorker(QThread):
    """Check the Grok API key / list models off the UI thread."""

    done = Signal(bool, str)

    def __init__(self, state: "AppState", parent=None) -> None:
        super().__init__(parent)
        self.state = state

    def run(self) -> None:
        try:
            ok, msg = self.state.grok.validate()
        except Exception as exc:  # noqa: BLE001
            ok, msg = False, str(exc)
        self.done.emit(ok, msg)
