"""Grok (xAI) cloud analysis — optional alternative/companion to Stockfish.

Sends ONLY the FEN + legal moves (and optionally Stockfish's lines as grounding)
to the xAI API when the user explicitly asks. Returns the same AnalysisResult
type as StockfishEngine so the Live page and overlay work unchanged.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Optional

import chess

from chess_engine.analysis_types import AnalysisLine, AnalysisResult, EvalScore
from storage.secret_store import redact_text


logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.x.ai/v1"
DEFAULT_GROK_MODEL = "grok-4-fast-reasoning"

_UCI_RE = re.compile(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b")


class GrokError(Exception):
    """User-presentable Grok/xAI failure (message already in Thai)."""


def extract_json_object(text: str) -> Optional[dict]:
    """Find and parse the first balanced {...} object in free-form text."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def parse_reply(text: str, board: chess.Board) -> tuple[Optional[chess.Move], str, str]:
    """Extract (legal move, explanation_th, eval_text) from Grok's reply.

    Prefers the JSON contract; falls back to scanning for UCI then SAN tokens.
    Never returns an illegal move.
    """
    explanation = ""
    eval_text = ""
    candidates: list[str] = []

    obj = extract_json_object(text)
    if obj:
        explanation = str(obj.get("explanation_th") or obj.get("explanation") or "").strip()
        eval_text = str(obj.get("eval_text") or obj.get("evaluation") or "").strip()
        uci = str(obj.get("move_uci") or "").strip().lower()
        if uci:
            candidates.append(uci)

    candidates.extend(m.group(1).lower() for m in _UCI_RE.finditer(text))

    for uci in candidates:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            continue
        if move in board.legal_moves:
            return move, explanation, eval_text

    # Last resort: SAN tokens like Nf3, O-O, exd5, e8=Q+
    for token in re.findall(r"[KQRBNOa-hx0-8=+#-]{2,7}", text):
        try:
            move = board.parse_san(token)
            return move, explanation, eval_text
        except ValueError:
            continue

    return None, explanation, eval_text


def build_prompt(board: chess.Board, hint: AnalysisResult | None = None) -> str:
    side = "White" if board.turn == chess.WHITE else "Black"
    legal = " ".join(m.uci() for m in board.legal_moves)
    parts = [
        f"FEN: {board.fen()}",
        f"Side to move: {side}",
        f"Legal moves (UCI): {legal}",
    ]
    if hint is not None and hint.ok:
        sf_lines = "; ".join(
            f"{ln.move_san} ({ln.score.format_display()})" for ln in hint.lines[:3]
        )
        parts.append(f"Stockfish top lines for reference: {sf_lines}")
    parts.append(
        "Pick the best move for the side to move (it MUST be one of the legal moves) "
        "and explain the idea in Thai for a club-level player. "
        'Reply with ONLY a JSON object, no other text: {"move_uci": "<uci>", '
        '"eval_text": "<short assessment in Thai>", '
        '"explanation_th": "<2-4 ประโยคภาษาไทย>"}'
    )
    return "\n".join(parts)


class GrokEngine:
    def __init__(
        self,
        api_key: str = "",
        model: str = DEFAULT_GROK_MODEL,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self.api_key = api_key
        self.model = model or DEFAULT_GROK_MODEL
        self.base_url = base_url.rstrip("/")

    def __repr__(self) -> str:  # pragma: no cover - safety for logs/debug
        has = "set" if self.api_key else "empty"
        return f"GrokEngine(model={self.model!r}, api_key={has}, base_url={self.base_url!r})"

    def configure(self, api_key: str, model: str) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip() or DEFAULT_GROK_MODEL

    def _request(self, path: str, payload: dict | None, timeout: float) -> dict:
        if not self.api_key:
            raise GrokError("ยังไม่ได้ใส่ Grok API Key (หน้า Engine)")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ChessVisionAssistant/0.1",
            },
            method="POST" if payload is not None else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:  # noqa: BLE001
                pass
            safe_body = redact_text(body)
            # Never log Authorization / key material (redacted body only)
            logger.warning("xAI HTTP %s: %s", exc.code, safe_body)
            if exc.code in (401, 403):
                raise GrokError("Grok API Key ไม่ถูกต้องหรือหมดอายุ") from None
            if exc.code == 404:
                raise GrokError(
                    f"ไม่พบโมเดล '{self.model}' — กด 'ตรวจสอบ Grok' เพื่อดูรายชื่อโมเดล"
                ) from None
            raise GrokError(
                f"xAI ตอบกลับผิดพลาด (HTTP {exc.code}): {safe_body}"
            ) from None
        except urllib.error.URLError as exc:
            raise GrokError(f"เชื่อมต่อ xAI ไม่ได้: {exc.reason}") from None
        except TimeoutError:
            raise GrokError("xAI ตอบช้าเกินไป (timeout)") from None

    def validate(self, timeout: float = 15.0) -> tuple[bool, str]:
        """Check key by listing available models (also helps pick a model name)."""
        try:
            data = self._request("/models", None, timeout)
        except GrokError as exc:
            return False, str(exc)
        names = [m.get("id", "") for m in data.get("data", []) if isinstance(m, dict)]
        if not names:
            return True, "Grok API Key ใช้งานได้"
        listed = ", ".join(sorted(n for n in names if n)[:12])
        ok_model = self.model in names
        note = "" if ok_model else f" (ไม่พบ '{self.model}' ในรายชื่อ)"
        return True, f"Grok พร้อมใช้งาน{note} — โมเดล: {listed}"

    def analyze(
        self,
        fen: str,
        *,
        hint: AnalysisResult | None = None,
        timeout: float = 90.0,
    ) -> AnalysisResult:
        result = AnalysisResult(fen=fen)
        try:
            board = chess.Board(fen)
        except ValueError as exc:
            result.error = f"FEN ไม่ถูกต้อง: {exc}"
            return result
        if board.is_game_over():
            result.error = "เกมจบแล้ว — ไม่มีการเดินให้วิเคราะห์"
            return result

        try:
            data = self._request(
                "/chat/completions",
                {
                    "model": self.model,
                    "temperature": 0.2,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a strong chess analyst. Always answer with the "
                                "exact JSON object requested and nothing else."
                            ),
                        },
                        {"role": "user", "content": build_prompt(board, hint)},
                    ],
                },
                timeout,
            )
        except GrokError as exc:
            result.error = str(exc)
            return result

        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            result.error = f"รูปแบบคำตอบจาก xAI ไม่ถูกต้อง: {str(data)[:200]}"
            return result

        move, explanation, eval_text = parse_reply(text, board)
        if move is None:
            result.error = f"Grok ไม่ได้ตอบการเดินที่ถูกกติกา — คำตอบ: {text[:300]}"
            return result

        san = board.san(move)
        if eval_text:
            explanation = f"{explanation} [ประเมิน: {eval_text}]" if explanation else eval_text
        result.lines = [
            AnalysisLine(
                multipv=1,
                move_uci=move.uci(),
                move_san=san,
                pv_uci=[move.uci()],
                pv_san=[san],
                score=EvalScore(),
                depth=0,
                explanation_th=explanation or f"Grok ({self.model}) แนะนำ {san}",
            )
        ]
        result.best_move_uci = move.uci()
        result.best_move_san = san
        return result
