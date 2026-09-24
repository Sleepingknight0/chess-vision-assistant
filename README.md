# Chess Vision Assistant

A Windows desktop side-panel application for recording chess moves by hand, analyzing the position with Stockfish, and drawing best-move guidance on a transparent overlay over the on-screen board.

The shipped UI is a PySide6 "God Board" window: you enter opponent moves yourself, Stockfish analyzes your turn, and you play the recommended move in the real game.

## Fair-play notice

Use this project only for personal study, training positions, and environments that explicitly permit external assistance.

The application does not control the mouse or play moves automatically. Users remain responsible for complying with the rules of every chess platform and event.

## How it works

1. Choose your side (**I play as**). Your pieces always appear at the bottom of the assistant board.
2. Align the overlay with **Position Overlay** so the four corners match the visible game board.
3. When the opponent moves, record it by clicking squares on the assistant board or the overlay (enable overlay click mode), or by entering UCI such as `e2e4` and pressing **Apply**.
4. On your turn, let Stockfish (or the opening book / tablebase) produce a recommendation.
5. Review the best-move arrow and candidate lines, then make the move yourself in the real game and confirm it with **Play best** (or **Play winning line** when you want the pressure-oriented PV).

## Key capabilities

- Manual legal-move tracking with castling, promotion, and en passant validation.
- Time-bounded Stockfish analysis with optional pondering while the opponent thinks.
- Polyglot opening-book lookup before the engine search.
- Syzygy tablebase path support (download helper covers three-to-five-piece sets).
- Transparent, click-through overlay with best-move arrows and translucent ghost pieces.
- Overlay corner calibration and temporary click mode for recording moves from the visible board.
- Position editor (**Set up pieces**) with FEN load/apply when the tracked board drifts.
- Redacted rotating logs under the user data directory.

Vision, capture (MSS / optional DXCam), move-detection, profile, PGN-export, and Grok helper packages remain in the repository, along with additional `gui/pages` modules. Those packages are **not wired into the current main window** launched by `python -m app`.

## Requirements

- Windows 10 or Windows 11.
- Python 3.12 or 3.13.
- A separately downloaded [Stockfish](https://stockfishchess.org/download/) executable.

Stockfish is not bundled with the source code or Windows build.

## Installation

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start the application from the repository root:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m app
```

The project can also be installed in editable mode with development and Windows extras:

```powershell
python -m pip install -e ".[dev,windows]"
```

The `windows` extra installs optional DXCam support used by the capture backends in the tree.

## Configure Stockfish

Download Stockfish from the official website, extract the Windows executable, and either:

- place it at `engines\stockfish.exe`; or
- select it with the application's **Stockfish…** button.

See [`engines/README.md`](engines/README.md) and [`scripts/download_stockfish_note.md`](scripts/download_stockfish_note.md) for details.

## Main controls

| Control | Action |
| --- | --- |
| Select two squares | Record a move on the assistant board or overlay |
| UCI + `Apply` | Record a move from notation such as `e2e4` |
| `Play best` | Apply the primary recommended move on your turn |
| `Play winning line` | Apply the pressure-oriented alternate line when available |
| `Re-analyze` | Request a fresh engine search |
| `Undo` | Revert the most recently recorded move |
| `New game` | Reset the tracked starting position |
| `Set up pieces…` | Open the FEN / position editor |
| `Overlay: Off/On` | Show or hide the transparent board overlay |
| `Position Overlay` | Drag the four-corner frame to match the visible board |
| `Overlay click: Off/On` | Temporarily capture clicks on the overlay for move entry |
| `Book…` / `Stockfish…` / `Tablebase…` | Choose opening book, engine binary, and Syzygy folder |

The overlay is click-through during normal play. Enable overlay click mode only while recording a move from the visible board. The floating overlay toolbar mirrors several of these actions (including **Play Best Move** and **Re-analyze**).

## Optional analysis resources

| Resource | Location | Purpose |
| --- | --- | --- |
| Stockfish | `engines/stockfish.exe` or a selected external path | UCI position analysis |
| Polyglot book | `engines/books/*.bin` or a selected external path | Opening move lookup |
| Syzygy tables | `engines/syzygy/` or a selected external path | Exact endgame analysis |

Download three-to-five-piece Syzygy tables with:

```powershell
python tools\download_syzygy_345.py
```

Engine binaries, opening books, and tablebases are intentionally excluded from Git.

## Testing

Run the unit-test suite and the import smoke test:

```powershell
pytest -q
python tools\smoke_import.py
```

The tests cover board orientation, grid mapping, FEN handling, legal move detection, special moves, automatic tracking helpers, PGN export helpers, perspective transforms, Grok response parsing, and secret storage.

## Build the Windows application

Create a PyInstaller build with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The output is written to `dist\ChessVisionAssistant\`. The build still requires the user to provide Stockfish separately. `build.spec` is also available for direct PyInstaller use.

## Repository structure

```text
.
|-- app/              # Entry point (`python -m app`), paths, and logging
|-- gui/              # God Board main window, theme, widgets; legacy pages under gui/pages/
|-- capture/          # MSS and optional DXCam backends (not used by current main UI)
|-- vision/           # Grid, perspective, occupancy, and stability helpers
|-- board_detection/  # Orientation and color mapping helpers
|-- move_detection/   # Candidate and automatic move-tracking helpers
|-- chess_core/       # Board state, FEN, validation, and special moves
|-- chess_engine/     # Stockfish, pondering, opening book, optional Grok helper
|-- overlay/          # Transparent overlay, setup frame, and toolbar
|-- profiles/         # Calibration profile models (library; not exposed in God Board)
|-- storage/          # Config helpers, DPAPI secret helpers, PGN export helpers
|-- engines/          # Gitignored local engine resources
|-- tests/            # Automated unit tests
|-- tools/            # Diagnostic and download utilities
|-- build.spec        # PyInstaller specification
`-- pyproject.toml    # Package metadata and Python requirements
```

## User data

Configuration and logs are stored under:

```text
%APPDATA%\ChessVisionAssistant\
```

Do not commit generated user data, screenshots, credentials, or third-party engine files.

## API keys and secrets

Optional Grok / xAI helper code can read `XAI_API_KEY` or `GROK_API_KEY` from the environment and can store a DPAPI-protected blob in config. The current God Board window does not expose a Grok analysis control. Diagnostics and logs redact common API-key and bearer-token patterns.

## Licensing

The application source is released under the [MIT License](LICENSE).

Stockfish is separate software distributed under the GNU General Public License. It is not bundled with this project; users download and operate it under the upstream license terms.
