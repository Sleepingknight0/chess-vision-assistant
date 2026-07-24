"""Grid square mapping tests."""

from board_detection.orientation import BoardOrientation
from vision.grid import BoardGrid, index_to_square_name, square_name_to_index


def test_square_index():
    assert square_name_to_index("a1") == (0, 0)
    assert square_name_to_index("h8") == (7, 7)
    assert index_to_square_name(4, 3) == "e4"


def test_grid_centers():
    g = BoardGrid(size=800, orientation=BoardOrientation())
    x0, y0, x1, y1 = g.cell_rect_square("a1")
    assert x1 > x0 and y1 > y0
    cx, cy = g.cell_center_square("a1")
    assert x0 <= cx <= x1


def test_pixel_to_square():
    g = BoardGrid(size=80, orientation=BoardOrientation())
    # center of bottom-left cell roughly a1
    sq = g.square_at_pixel(5, 75)
    assert sq == "a1"


def test_all_64_unique():
    g = BoardGrid(orientation=BoardOrientation())
    squares = [sq for sq, _ in g.iter_cells()]
    assert len(squares) == 64
    assert len(set(squares)) == 64
