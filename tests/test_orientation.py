"""Board orientation tests."""

from board_detection.orientation import BoardOrientation


def test_white_bottom_a1():
    o = BoardOrientation(rotation_deg=0, my_pieces_at_bottom=True, user_is_white=True)
    col, row = o.square_to_display("a1")
    assert (col, row) == (0, 7)
    assert o.display_to_square(0, 7) == "a1"


def test_white_bottom_h1():
    o = BoardOrientation(user_is_white=True, my_pieces_at_bottom=True)
    assert o.square_to_display("h1") == (7, 7)
    assert o.display_to_square(7, 7) == "h1"


def test_black_at_bottom_flips():
    o = BoardOrientation(user_is_white=False, my_pieces_at_bottom=True)
    # a1 should appear top-right-ish when black at bottom (180 rot)
    col, row = o.square_to_display("a1")
    assert o.display_to_square(col, row) == "a1"
    # e2 for white becomes top area
    assert o.effective_rotation() == 180


def test_rotation_90_roundtrip():
    o = BoardOrientation(rotation_deg=90, user_is_white=True, my_pieces_at_bottom=True)
    for sq in ["a1", "e4", "h8", "d5"]:
        c, r = o.square_to_display(sq)
        assert o.display_to_square(c, r) == sq
