# Local Chess Engines and Data

This directory is reserved for large third-party analysis files used by Chess Vision Assistant. These files are intentionally excluded from Git.

## Supported resources

| Resource              | Recommended location       | Installation                                                                                                               |
| --------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Stockfish             | `engines/stockfish.exe`    | Download the Windows build from [stockfishchess.org](https://stockfishchess.org/download/) and extract the executable here |
| Polyglot opening book | `engines/books/<name>.bin` | Supply a compatible book and select it through the application                                                             |
| Syzygy tablebases     | `engines/syzygy/`          | Run `python tools/download_syzygy_345.py` for the supported three-to-five-piece set                                        |

Resources can also remain elsewhere on the computer and be selected through the application settings.

## Stockfish setup

1. Download the official Windows package.
2. Choose an AVX2 or generic build that matches the target computer.
3. Extract the executable.
4. Place it at `engines\stockfish.exe` or select its external path in the application.
5. Start an analysis to confirm that the UCI process launches correctly.

See [`../scripts/download_stockfish_note.md`](../scripts/download_stockfish_note.md) for the standalone installation note.

## Version-control policy

Do not commit engine executables, opening books, tablebase files, downloaded archives, or generated analysis data.

Third-party resources retain their original licences. Stockfish is distributed under the GNU General Public License and remains separate from this MIT-licensed application.
