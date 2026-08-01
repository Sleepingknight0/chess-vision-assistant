# Chess Vision Assistant

A Windows desktop application for board calibration, move tracking, position analysis, and visual Stockfish guidance.

The application combines a PySide6 interface with screen capture, computer vision, chess-rule validation, and optional analysis engines.

## Fair-play notice

Use this project only for personal study, training positions, and environments that explicitly permit external assistance.

The application does not control the mouse or play moves automatically. Users remain responsible for complying with the rules of every chess platform and event.

## How it works

1. Select your side and calibrate the on-screen board.
2. Record the opponent's move by selecting squares or entering UCI notation such as `e2e4`.
3. Allow Stockfish to analyze the current legal position.
4. Review the best-move arrow and candidate lines.
5. Make the move yourself and confirm it in the assistant.

The bottom of the assistant board always represents the user; the top represents the opponent.

## Key capabilities

- Calibrated screen capture with MSS and optional DXCam support.
- Board orientation, grid, perspective, occupancy, and drift handling.
- Legal move tracking, including castling, promotion, and en passant.
- Time-bounded Stockfish analysis with optional pondering.
- Polyglot opening-book support.
- Syzygy endgame tablebase support for positions with up to five pieces.
- Transparent best-move and ghost-board overlays.
- Reusable calibration profiles.
- PGN export, diagnostics, and redacted logs.
- Optional Grok analysis initiated only by the user.

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

## Configure Stockfish

Download Stockfish from the official website, extract the Windows executable, and either:

- place it at `engines\stockfish.exe`; or
- select it through the application's **Stockfish** file picker.

See [`engines/README.md`](engines/README.md) and [`scripts/download_stockfish_note.md`](scripts/download_stockfish_note.md) for details.

## Main controls

| Control            | Action                                                |
| ------------------ | ----------------------------------------------------- |
| Select two squares | Record a move                                         |
| `Play Best Move`   | Record the move recommended for the user's turn       |
| `Re-analyze`       | Request a new engine analysis                         |
| `Undo`             | Revert the most recently recorded move                |
| `New game`         | Reset the tracked position                            |
| `Position Overlay` | Align the overlay corners with the visible board      |
| `Click Overlay`    | Temporarily capture overlay clicks for move recording |

The overlay is click-through during normal operation. Enable click mode only while recording a move directly from the visible board.

## Optional analysis resources

| Resource      | Location                                            | Purpose                |
| ------------- | --------------------------------------------------- | ---------------------- |
| Stockfish     | `engines/stockfish.exe` or a selected external path | UCI position analysis  |
| Polyglot book | `engines/books/*.bin` or a selected external path   | Opening move lookup    |
| Syzygy tables | `engines/syzygy/` or a selected external path       | Exact endgame analysis |

Download three-to-five-piece Syzygy tables with:

```powershell
python tools\download_syzygy_345.py
```

Engine binaries, opening books, and tablebases are intentionally excluded from Git.

## Testing

Run the unit suite and import smoke test:

```powershell
pytest -q
python tools\smoke_import.py
```

The tests cover board orientation, grid mapping, FEN handling, legal move detection, special moves, automatic tracking, PGN export, perspective transforms, and secret storage.

## Build the Windows application

Create a PyInstaller build with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The output is written to `dist\ChessVisionAssistant\`. The build still requires the user to provide Stockfish separately.

## Repository structure

```text
.
|-- app/                         # Entry point, paths, and logging
|-- gui/                         # Main window, pages, state, and widgets
|-- capture/                     # MSS and optional DXCam capture backends
|-- vision/                      # Grid, perspective, occupancy, and stability logic
|-- board_detection/             # Orientation and color mapping
|-- move_detection/              # Candidate and automatic move tracking
|-- chess_core/                  # Board state, FEN, validation, and special moves
|-- chess_engine/                # Stockfish, pondering, books, and optional Grok
|-- overlay/                     # Transparent overlay and positioning interface
|-- profiles/                    # Calibration profile models and management
|-- storage/                     # Configuration, DPAPI secrets, and PGN export
|-- engines/                     # Gitignored local engine resources
|-- tests/                       # Automated unit tests
|-- tools/                       # Diagnostic and download utilities
|-- build.spec                   # PyInstaller specification
`-- pyproject.toml               # Package metadata and Python requirements
```

## User data

Configuration, profiles, logs, and exports are stored under:

```text
%APPDATA%\ChessVisionAssistant\
```

Do not commit generated user data, screenshots, credentials, or third-party engine files.

## Optional Grok integration

Grok requests occur only after the user triggers the feature. The request contains the current FEN, legal moves, and available Stockfish lines.

Prefer an environment variable for temporary use:

```powershell
$env:XAI_API_KEY = "your-api-key"
python -m app
```

`GROK_API_KEY` is also supported. When saved through the application, the key is protected with Windows DPAPI instead of being stored as plaintext in `config.json`.

Diagnostics redact common API-key and bearer-token patterns before display or export.

## Licensing

The application source is released under the [MIT License](LICENSE).

Stockfish is separate software distributed under the GNU General Public License. It is not bundled with this project; users download and operate it under the upstream licence terms.
