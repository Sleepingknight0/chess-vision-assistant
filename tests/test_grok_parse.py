"""Grok reply parsing — no network involved."""

from __future__ import annotations

import chess

from chess_engine.grok_engine import (
    GrokEngine,
    build_prompt,
    extract_json_object,
    parse_reply,
)


def test_extract_json_plain():
    obj = extract_json_object('{"move_uci": "e2e4", "explanation": "controls the center"}')
    assert obj == {"move_uci": "e2e4", "explanation": "controls the center"}


def test_extract_json_in_fenced_block():
    text = 'Here you go:\n```json\n{"move_uci": "g1f3", "eval_text": "+0.3"}\n```\nEnjoy.'
    obj = extract_json_object(text)
    assert obj["move_uci"] == "g1f3"


def test_extract_json_with_braces_in_strings():
    obj = extract_json_object(
        '{"move_uci": "e2e4", "explanation": "opens {space} for the bishop"}'
    )
    assert obj["move_uci"] == "e2e4"


def test_extract_json_none_when_missing():
    assert extract_json_object("no json here, just e2e4 talk") is None


def test_parse_reply_json_legal_move():
    board = chess.Board()
    move, explanation, eval_text = parse_reply(
        '{"move_uci": "e2e4", "eval_text": "equal", "explanation": "controls the center"}',
        board,
    )
    assert move == chess.Move.from_uci("e2e4")
    assert explanation == "controls the center"
    assert eval_text == "equal"


def test_parse_reply_legacy_explanation_th():
    """Backward compat: still accept explanation_th from older replies."""
    board = chess.Board()
    move, explanation, eval_text = parse_reply(
        '{"move_uci": "e2e4", "eval_text": "equal", "explanation_th": "controls the center"}',
        board,
    )
    assert move == chess.Move.from_uci("e2e4")
    assert explanation == "controls the center"
    assert eval_text == "equal"


def test_parse_reply_rejects_illegal_json_move_falls_back_to_text():
    board = chess.Board()
    # JSON claims an illegal move; a legal UCI appears later in prose
    move, _, _ = parse_reply(
        '{"move_uci": "e2e5"} but actually d2d4 is the right move', board
    )
    assert move == chess.Move.from_uci("d2d4")


def test_parse_reply_uci_from_prose():
    board = chess.Board()
    move, _, _ = parse_reply("I recommend g1f3 developing the knight.", board)
    assert move == chess.Move.from_uci("g1f3")


def test_parse_reply_promotion_uci():
    board = chess.Board("8/P7/8/8/8/8/7k/K7 w - - 0 1")
    move, _, _ = parse_reply('{"move_uci": "a7a8q"}', board)
    assert move == chess.Move.from_uci("a7a8q")


def test_parse_reply_san_fallback():
    board = chess.Board()
    move, _, _ = parse_reply("Best is Nf3 here.", board)
    assert move == chess.Move.from_uci("g1f3")


def test_parse_reply_no_move():
    board = chess.Board()
    move, _, _ = parse_reply("I cannot analyze this position, sorry!", board)
    assert move is None


def test_build_prompt_contains_fen_and_legal_moves():
    board = chess.Board()
    prompt = build_prompt(board)
    assert board.fen() in prompt
    assert "e2e4" in prompt
    assert "move_uci" in prompt
    assert "explanation" in prompt
    assert "English" in prompt


def test_analyze_without_key_returns_error():
    eng = GrokEngine(api_key="")
    result = eng.analyze(chess.Board().fen())
    assert not result.ok
    assert "API Key" in result.error


def test_analyze_rejects_bad_fen():
    eng = GrokEngine(api_key="xai-test")
    result = eng.analyze("not a fen")
    assert not result.ok
    assert result.error
