"""Smoke import for Chess Vision Assistant."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULES = [
    "app.main",
    "app.paths",
    "chess_core.board_state",
    "chess_core.fen_utils",
    "chess_engine.stockfish_engine",
    "chess_engine.ponder",
    "chess_engine.opening_book",
    "chess_engine.worker",
    "board_detection.orientation",
    "gui.theme",
    "gui.widgets.board_view",
    "gui.god_board",
    "gui.main_window",
    "overlay.overlay_window",
    "overlay.setup_frame",
    "overlay.toolbar",
]


def main() -> int:
    failed = []
    for name in MODULES:
        try:
            importlib.import_module(name)
            print(f"OK  {name}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {name}: {exc}")
            failed.append(name)
    print(f"\n{len(MODULES) - len(failed)}/{len(MODULES)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
