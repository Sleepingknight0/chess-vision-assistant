"""Perspective transform tests."""

from __future__ import annotations

import numpy as np

from vision.perspective import PerspectiveCalibration, default_corners


def test_default_corners_count():
    c = default_corners(100, 200)
    assert len(c) == 4


def test_warp_identity_like():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[10:90, 10:90] = (0, 255, 0)
    cal = PerspectiveCalibration(
        corners=[(10, 10), (90, 10), (90, 90), (10, 90)],
        warped_size=64,
    )
    out = cal.warp(img)
    assert out.shape == (64, 64, 3)
    assert out.mean() > 0


def test_roundtrip_mapping():
    cal = PerspectiveCalibration(
        corners=[(0, 0), (100, 0), (100, 100), (0, 100)],
        warped_size=100,
    )
    bx, by = cal.image_to_board_xy(50, 50)
    ix, iy = cal.board_xy_to_image(bx, by)
    assert abs(ix - 50) < 1.5
    assert abs(iy - 50) < 1.5


def test_from_list():
    cal = PerspectiveCalibration.from_list([[1, 2], [3, 4], [5, 6], [7, 8]], 256)
    assert cal.warped_size == 256
    assert cal.corners[0] == (1.0, 2.0)
