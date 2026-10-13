"""Synthetic hand landmarks for gesture unit tests."""
from __future__ import annotations

import numpy as np


def make_hand(
    index: bool = False,
    middle: bool = False,
    ring: bool = False,
    pinky: bool = False,
    thumb: bool = False,
    thumb_up: bool = False,
    pinch: bool = False,
) -> np.ndarray:
    """Build a 21x3 landmark array for a synthetic, upright hand."""
    pts = np.zeros((21, 3), dtype=float)
    pts[0] = [0.50, 0.75, 0.0]

    if thumb_up:
        pts[1] = [0.50, 0.68, 0.0]
        pts[2] = [0.50, 0.60, 0.0]
        pts[3] = [0.49, 0.51, 0.0]
        pts[4] = [0.48, 0.42, 0.0]
    elif thumb or pinch:
        pts[1] = [0.46, 0.68, 0.0]
        pts[2] = [0.42, 0.62, 0.0]
        pts[3] = [0.38, 0.58, 0.0]
        pts[4] = [0.34, 0.56, 0.0]
    else:
        pts[1] = [0.46, 0.68, 0.0]
        pts[2] = [0.44, 0.63, 0.0]
        pts[3] = [0.45, 0.62, 0.0]
        pts[4] = [0.46, 0.62, 0.0]

    def finger(mcp_index: int, mcp_xy: tuple, extended: bool) -> None:
        mcp = np.array([mcp_xy[0], mcp_xy[1], 0.0])
        pts[mcp_index] = mcp
        if extended:
            pts[mcp_index + 1] = mcp + [0.0, -0.06, 0.0]
            pts[mcp_index + 2] = mcp + [0.0, -0.09, 0.0]
            pts[mcp_index + 3] = mcp + [0.0, -0.12, 0.0]
        else:
            pts[mcp_index + 1] = mcp + [0.0, -0.05, 0.0]
            pts[mcp_index + 2] = mcp + [0.0, -0.02, 0.0]
            pts[mcp_index + 3] = mcp + [0.0, 0.02, 0.0]

    finger(5, (0.52, 0.55), index)
    finger(9, (0.53, 0.55), middle)
    finger(13, (0.54, 0.56), ring)
    finger(17, (0.55, 0.58), pinky)

    if pinch:
        pts[3] = [0.45, 0.53, 0.0]
        pts[4] = [0.47, 0.52, 0.0]
        pts[8] = [0.42, 0.48, 0.0]
        pts[7] = [0.45, 0.50, 0.0]
        pts[6] = [0.48, 0.52, 0.0]

    return pts
