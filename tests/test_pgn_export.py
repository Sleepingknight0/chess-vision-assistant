"""PGN export tests."""

from storage.pgn_export import classify_loss, pgn_from_uci_list


def test_pgn_basic():
    pgn = pgn_from_uci_list(["e2e4", "e7e5"], white="Light Cherry", black="Dark Cherry")
    assert "Light Cherry" in pgn
    assert "Dark Cherry" in pgn
    assert "e4" in pgn or "1." in pgn


def test_classify_loss():
    assert classify_loss(10) == "best"
    assert classify_loss(120) == "inaccuracy"
    assert classify_loss(200) == "mistake"
    assert classify_loss(400) == "blunder"
