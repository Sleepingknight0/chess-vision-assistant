# Build Chess Vision Assistant with PyInstaller (Windows)
# Does NOT bundle stockfish.exe — user must provide separately.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Building from $Root"

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "Creating venv..."
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install "pyinstaller>=6.0"

Write-Host "Running PyInstaller..."
.\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --windowed `
    --name ChessVisionAssistant `
    --add-data "assets;assets" `
    --add-data "config.example.json;." `
    --hidden-import chess `
    --hidden-import chess.engine `
    --hidden-import mss `
    --hidden-import cv2 `
    --collect-all PySide6 `
    app\main.py

Write-Host "Done. Output: dist\ChessVisionAssistant\"
Write-Host "Place stockfish.exe separately and select it in the app (Stockfish…)."
