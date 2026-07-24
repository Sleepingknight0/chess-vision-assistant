"""Stockfish UCI subprocess wrapper (local only)."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

import chess
import chess.engine

from chess_engine.analysis_types import AnalysisLine, AnalysisResult, EvalScore


logger = logging.getLogger(__name__)


PRESETS = {
    "fast": {"movetime_ms": 150, "label": "เร็ว (100–200 ms)"},
    "balanced": {"movetime_ms": 750, "label": "สมดุล (500–1000 ms)"},
    "deep": {"movetime_ms": 3500, "label": "ลึก (2–5 วินาที)"},
}


class StockfishEngine:
    def __init__(self, path: str = "") -> None:
        self.path = path
        self.syzygy_path = ""  # folder of Syzygy tablebases → perfect endgames
        self._engine: Optional[chess.engine.SimpleEngine] = None

    def set_path(self, path: str) -> None:
        self.close()
        self.path = path

    def set_syzygy_path(self, path: str) -> None:
        self.syzygy_path = path or ""

    def close(self) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Engine quit error: %s", exc)
            self._engine = None

    def validate(self) -> tuple[bool, str]:
        if not self.path:
            return False, "ยังไม่ได้เลือกไฟล์ stockfish.exe"
        p = Path(self.path)
        if not p.is_file():
            return False, f"ไม่พบ Stockfish: {self.path}"
        try:
            eng = chess.engine.SimpleEngine.popen_uci(self.path)
            eng.quit()
            return True, "Stockfish พร้อมใช้งาน"
        except Exception as exc:  # noqa: BLE001
            logger.exception("Stockfish validate failed")
            return False, f"เปิด Engine ไม่ได้: {exc}"

    def _ensure(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            if not self.path or not Path(self.path).is_file():
                raise FileNotFoundError("ไม่พบ Stockfish")
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        return self._engine

    def configure(
        self,
        threads: int = 2,
        skill_level: Optional[int] = None,
        hash_mb: int = 128,
    ) -> None:
        eng = self._ensure()
        # Use available cores (leave one for the OS/UI); allow a big hash.
        cores = os.cpu_count() or 4
        safe_threads = max(1, min(int(threads), max(1, cores)))
        opts: dict = {"Threads": safe_threads, "Hash": max(16, min(hash_mb, 2048))}
        if skill_level is not None:
            opts["Skill Level"] = max(0, min(20, skill_level))
        # Guarantee full strength — never Elo-limited — at max skill
        if skill_level is None or skill_level >= 20:
            opts["UCI_LimitStrength"] = False
        # Syzygy tablebases → provably perfect play in ≤7-piece endgames
        if self.syzygy_path and Path(self.syzygy_path).is_dir():
            opts["SyzygyPath"] = self.syzygy_path
        try:
            eng.configure(opts)
        except Exception as exc:  # noqa: BLE001
            logger.warning("configure partial fail: %s", exc)
            try:
                eng.configure({"Threads": safe_threads, "Hash": 128})
            except Exception as exc2:  # noqa: BLE001
                logger.warning("configure failed: %s", exc2)

    def analyze(
        self,
        fen: str,
        *,
        movetime_ms: Optional[int] = None,
        depth: Optional[int] = None,
        multipv: int = 1,
        threads: int = 2,
        skill_level: Optional[int] = None,
        hash_mb: int = 128,
    ) -> AnalysisResult:
        multipv = max(1, min(5, multipv))
        result = AnalysisResult(fen=fen)
        try:
            board = chess.Board(fen)
        except ValueError as exc:
            result.error = f"FEN ไม่ถูกต้อง: {exc}"
            return result

        try:
            eng = self._ensure()
            self.configure(threads=threads, skill_level=skill_level, hash_mb=hash_mb)
            limit = (
                chess.engine.Limit(time=movetime_ms / 1000.0)
                if movetime_ms
                else chess.engine.Limit(depth=depth or 15)
            )
            info = eng.analyse(board, limit, multipv=multipv)
            if not isinstance(info, list):
                info = [info]

            lines: list[AnalysisLine] = []
            for i, item in enumerate(info):
                pv = item.get("pv") or []
                if not pv:
                    continue
                score_obj = item.get("score")
                eval_score = _score_to_eval(score_obj, board.turn)
                san_moves: list[str] = []
                uci_moves: list[str] = []
                temp = board.copy()
                for m in pv:
                    try:
                        san_moves.append(temp.san(m))
                        uci_moves.append(m.uci())
                        temp.push(m)
                    except Exception:  # noqa: BLE001
                        break
                best = pv[0]
                line = AnalysisLine(
                    multipv=i + 1,
                    move_uci=best.uci(),
                    move_san=san_moves[0] if san_moves else best.uci(),
                    pv_uci=uci_moves,
                    pv_san=san_moves,
                    score=eval_score,
                    depth=int(item.get("depth") or 0),
                    explanation_th=explain_move_th(board, best, san_moves[0] if san_moves else best.uci()),
                )
                lines.append(line)

            result.lines = lines
            if lines:
                result.best_move_uci = lines[0].move_uci
                result.best_move_san = lines[0].move_san
                result.evaluation = lines[0].score
        except FileNotFoundError:
            result.error = "ไม่พบ Stockfish — เลือกไฟล์ stockfish.exe ในหน้า Engine"
        except Exception as exc:  # noqa: BLE001
            logger.exception("analyze failed")
            result.error = f"วิเคราะห์ไม่สำเร็จ: {exc}"
            self.close()
        return result


def build_analysis_result(board: chess.Board, infos, fen: str) -> AnalysisResult:
    """Build an AnalysisResult from python-chess info dicts (one per MultiPV).

    Used by the streaming/continuous analyzer, which accumulates the latest
    info line per multipv index and rebuilds the result as depth grows.
    """
    result = AnalysisResult(fen=fen)
    lines: list[AnalysisLine] = []
    for item in sorted(infos, key=lambda x: x.get("multipv", 1)):
        pv = item.get("pv") or []
        if not pv:
            continue
        eval_score = _score_to_eval(item.get("score"), board.turn)
        san_moves: list[str] = []
        uci_moves: list[str] = []
        temp = board.copy()
        for m in pv:
            try:
                san_moves.append(temp.san(m))
                uci_moves.append(m.uci())
                temp.push(m)
            except Exception:  # noqa: BLE001
                break
        best = pv[0]
        lines.append(
            AnalysisLine(
                multipv=int(item.get("multipv", len(lines) + 1)),
                move_uci=best.uci(),
                move_san=san_moves[0] if san_moves else best.uci(),
                pv_uci=uci_moves,
                pv_san=san_moves,
                score=eval_score,
                depth=int(item.get("depth") or 0),
                explanation_th=explain_move_th(
                    board, best, san_moves[0] if san_moves else best.uci()
                ),
            )
        )
    lines.sort(key=lambda ln: ln.multipv)
    result.lines = lines
    if lines:
        result.best_move_uci = lines[0].move_uci
        result.best_move_san = lines[0].move_san
        result.evaluation = lines[0].score
    return result


def _score_to_eval(score_obj: object, turn: chess.Color) -> EvalScore:
    if score_obj is None:
        return EvalScore()
    try:
        # python-chess Score: relative to side to move; convert to white POV
        pov = score_obj.white()  # type: ignore[attr-defined]
        if pov.is_mate():
            return EvalScore(mate=pov.mate())
        return EvalScore(cp=pov.score())
    except Exception:  # noqa: BLE001
        return EvalScore()


def explain_move_th(board: chess.Board, move: chess.Move, san: str) -> str:
    """Rule-based Thai explanation (no cloud LLM)."""
    parts: list[str] = []
    fr = chess.square_name(move.from_square)
    to = chess.square_name(move.to_square)
    parts.append(f"แนะนำให้เดินจาก {fr} ไป {to}")

    if board.is_castling(move):
        if move.to_square > move.from_square:
            parts.append("เป็นการโรเคดด้านคิง (Kingside Castling)")
        else:
            parts.append("เป็นการโรเคดด้านควีน (Queenside Castling)")
    if board.is_en_passant(move):
        parts.append("เป็นการกินแบบ En Passant")
    if board.is_capture(move) and not board.is_en_passant(move):
        parts.append("เป็นการกินหมาก (Capture)")
    if move.promotion:
        names = {
            chess.QUEEN: "ควีน",
            chess.ROOK: "เรือ",
            chess.BISHOP: "บิชอป",
            chess.KNIGHT: "ม้า",
        }
        parts.append(f"โปรโมทเป็น{names.get(move.promotion, 'หมาก')}")

    piece = board.piece_at(move.from_square)
    if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        from_rank = chess.square_rank(move.from_square)
        if (piece.color == chess.WHITE and from_rank == 0) or (
            piece.color == chess.BLACK and from_rank == 7
        ):
            parts.append("เพื่อพัฒนาหมากออกจากแถวหลัง")

    if to in {"d4", "d5", "e4", "e5"}:
        parts.append("เพื่อควบคุมช่องกลาง")

    # Check / mate after move
    temp = board.copy()
    try:
        temp.push(move)
        if temp.is_checkmate():
            parts.append("รุกจนหมาก!")
        elif temp.is_check():
            parts.append("เป็นการรุกคิง (Check)")
    except Exception:  # noqa: BLE001
        pass

    return " ".join(parts)


def find_stockfish_hint() -> str:
    which = shutil.which("stockfish")
    if which:
        return which
    return ""
