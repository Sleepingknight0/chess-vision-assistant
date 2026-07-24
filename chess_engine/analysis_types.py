"""Types for engine analysis results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvalScore:
    """Centipawn or mate score from White's perspective (UCI convention)."""

    cp: Optional[int] = None
    mate: Optional[int] = None

    def format_display(self) -> str:
        if self.mate is not None:
            sign = "+" if self.mate > 0 else "-"
            return f"Mate in {abs(self.mate)}" if self.mate != 0 else "Mate"
        if self.cp is not None:
            return f"{self.cp / 100.0:+.2f}"
        return "—"

    def as_pawns(self) -> Optional[float]:
        if self.mate is not None:
            return 100.0 if self.mate > 0 else -100.0
        if self.cp is not None:
            return self.cp / 100.0
        return None


@dataclass
class AnalysisLine:
    multipv: int
    move_uci: str
    move_san: str
    pv_uci: list[str] = field(default_factory=list)
    pv_san: list[str] = field(default_factory=list)
    score: EvalScore = field(default_factory=EvalScore)
    depth: int = 0
    explanation_th: str = ""


@dataclass
class AnalysisResult:
    fen: str
    lines: list[AnalysisLine] = field(default_factory=list)
    best_move_uci: str = ""
    best_move_san: str = ""
    evaluation: EvalScore = field(default_factory=EvalScore)
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.best_move_uci) and not self.error
