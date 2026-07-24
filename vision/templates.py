"""Piece template library for recovery / non-standard starts (Phase 3)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.paths import templates_dir

logger = logging.getLogger(__name__)

PIECE_KEYS = ["P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k"]


@dataclass
class TemplateLibrary:
    """Multiple image templates per piece symbol."""

    root: Path = field(default_factory=templates_dir)
    templates: dict[str, list[np.ndarray]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.load()

    def load(self) -> None:
        self.templates = {k: [] for k in PIECE_KEYS}
        meta_path = self.root / "index.json"
        if not meta_path.is_file():
            return
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            for symbol, files in meta.items():
                for rel in files:
                    path = self.root / rel
                    if path.is_file():
                        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                        if img is not None:
                            self.templates.setdefault(symbol, []).append(img)
        except Exception as exc:  # noqa: BLE001
            logger.warning("template load failed: %s", exc)

    def save_index(self) -> None:
        meta: dict[str, list[str]] = {}
        for symbol, images in self.templates.items():
            files = []
            for i, _img in enumerate(images):
                rel = f"{symbol}_{i}.png"
                files.append(rel)
            meta[symbol] = files
        (self.root / "index.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

    def add_sample(self, symbol: str, bgr: np.ndarray) -> None:
        if symbol not in PIECE_KEYS:
            raise ValueError(f"Unknown piece symbol: {symbol}")
        imgs = self.templates.setdefault(symbol, [])
        idx = len(imgs)
        path = self.root / f"{symbol}_{idx}.png"
        crop = cv2.resize(bgr, (64, 64))
        cv2.imwrite(str(path), crop)
        imgs.append(crop)
        self.save_index()

    def count(self, symbol: str | None = None) -> int:
        if symbol:
            return len(self.templates.get(symbol, []))
        return sum(len(v) for v in self.templates.values())

    def match_cell(self, cell_bgr: np.ndarray) -> tuple[Optional[str], float]:
        """Return best (symbol, score). Score is TM_CCOEFF_NORMED 0..1.

        Not claimed perfect for 3D — use for recovery hints only.
        """
        if cell_bgr is None or cell_bgr.size == 0:
            return None, 0.0
        query = cv2.resize(cell_bgr, (64, 64))
        best_sym: Optional[str] = None
        best_score = 0.0
        for symbol, imgs in self.templates.items():
            for tmpl in imgs:
                if tmpl.shape[:2] != (64, 64):
                    tmpl = cv2.resize(tmpl, (64, 64))
                res = cv2.matchTemplate(query, tmpl, cv2.TM_CCOEFF_NORMED)
                score = float(res[0, 0])
                if score > best_score:
                    best_score = score
                    best_sym = symbol
        if best_score < 0.55:
            return None, best_score
        return best_sym, best_score

    def classify_board(
        self, warped_bgr: np.ndarray, occupied_map: dict[str, bool], grid
    ) -> dict[str, str]:
        """Map square -> piece symbol for occupied cells (best effort)."""
        result: dict[str, str] = {}
        for sq, occ in occupied_map.items():
            if not occ:
                continue
            crop = grid.crop_cell(warped_bgr, sq, center_fraction=0.7)
            sym, score = self.match_cell(crop)
            if sym:
                result[sq] = sym
        return result
