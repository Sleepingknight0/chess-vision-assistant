# Chess Vision Assistant

Windows desktop app (PySide6) — on-screen **chess play assistant** with **Stockfish** analysis.

> **Scope:** for practice / analysis only  
> The app does **not** control the mouse, does not auto-play moves in the game, and does not bypass anti-cheat.

## Concept

| On the board | Meaning |
|--------------|---------|
| **Bottom** | Always you |
| **Top** | Opponent |

1. You **enter the opponent's moves yourself** (click squares or type `e2e4`)
2. Your turn → Stockfish analyzes and shows a Best Move arrow
3. You make the move in the real game following the arrow, then press **Play Best Move**

## Requirements

- Windows 10/11
- Python **3.12–3.13**
- [Stockfish](https://stockfishchess.org/download/) (downloaded separately — GPL, not bundled in the build)

## Install & run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:PYTHONPATH = (Get-Location).Path
python -m app
```

Place `engines\stockfish.exe` or pick the path in the app with the **Stockfish…** button.  
Details: [`engines/README.md`](engines/README.md) · [`scripts/download_stockfish_note.md`](scripts/download_stockfish_note.md)

## Main features

- Side-screen assistant board + Always on top
- Time-bounded analysis (does not burn CPU continuously) + **ponder** (think ahead on the opponent's turn)
- **Opening Book** (polyglot `.bin`) — toggle with the **Book** checkbox
- **Syzygy tablebase** — endgames with ≤5 pieces (place under `engines/syzygy/` or run `python tools/download_syzygy_345.py`)
- **Overlay** on the real game — Best Move arrow / ghost board / click-to-record move mode
- Side choice: White (Light Cherry) / Black (Dark Cherry)

## Main buttons

| Button | Action |
|--------|--------|
| Click from→to | Record a move |
| **Play Best Move** | Record your turn from Stockfish |
| **Re-analyze** | Ask the engine to think again |
| **Undo** / **New game** | Undo / start a new game |
| **Position Overlay** | Drag corners 1–4 onto the in-game board |

In normal mode the Overlay is click-through — clicks pass through to the game.  
When **Click Overlay** is on, clicks do not pass through (used to record moves on the game board).

## Tests

```powershell
pytest -q
python tools\smoke_import.py
```

## Build .exe (optional)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

`stockfish.exe` is **not** bundled — users install it themselves.

## Project layout (summary)

```
app/            entry point
gui/            Assistant UI + widgets
chess_core/     FEN / validation / special moves
chess_engine/   Stockfish UCI, ponder, opening book
overlay/        transparent overlay + setup frame
profiles/       calibration profiles (persist)
storage/        config + PGN export
engines/        local Stockfish / book / syzygy (gitignored binaries)
tests/          unit tests (logic only)
```

User data is stored under `%APPDATA%\ChessVisionAssistant\` (config, profiles, logs, exports)

## Security (API keys)

- **Do not** put real API keys in the repo / `config.example.json` / commits
- Grok/xAI keys are stored on the machine via **Windows DPAPI** (`grok_api_key_protected`) — **not** written as plain text in `config.json`
- Prefer setting via environment (does not touch the app's disk):

```powershell
$env:XAI_API_KEY = "xai-..."   # or GROK_API_KEY
python -m app
```

- Logs / Diagnostics page automatically **redact** `xai-…` / `Bearer …` patterns
- Grok is called only when the user presses the button — only FEN + legal moves are sent (and Stockfish lines if available)

## License

Code in this repo is licensed as stated in the repository.  
**Stockfish** is separate software under the **GPL** — download and use it under upstream terms.
