"""Team / skin mapping tests."""

from board_detection.color_mapping import TeamMapping, default_team_mapping


def test_defaults_light_dark_cherry():
    m = default_team_mapping(True)
    assert m.white_label == "Light Cherry"
    assert m.black_label == "Dark Cherry"
    assert m.user_label() == "Light Cherry"
    assert m.opponent_label() == "Dark Cherry"


def test_user_black():
    m = TeamMapping(user_is_white=False)
    assert m.user_label() == "Dark Cherry"


def test_side_from_label():
    m = TeamMapping()
    assert m.side_from_label("Light Cherry") is True
    assert m.side_from_label("Dark Cherry") is False
