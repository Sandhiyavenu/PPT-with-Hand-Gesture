"""Virtual pointer support.

When pointer mode is enabled the index fingertip drives the real OS cursor.
Only active on Windows; on other platforms it degrades to a no-op so the rest
of the app keeps working.
"""
from __future__ import annotations

import sys
import threading
from typing import Optional, Tuple

from . import config

_IS_WINDOWS = sys.platform.startswith("win")


def _screen_size() -> Tuple[int, int]:
    import ctypes

    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


class VirtualPointer:
    """Maps a normalised camera point to the screen cursor."""

    def __init__(self, margin: float = config.POINTER_MARGIN,
                 smoothing: float = config.POINTER_SMOOTHING) -> None:
        self.margin = margin
        self.smoothing = smoothing
        self._smoothed: Optional[Tuple[float, float]] = None
        self._lock = threading.Lock()

    def _normalise(self, x: float, y: float) -> Tuple[float, float]:
        span = 1.0 - 2 * self.margin
        nx = (x - self.margin) / span if span > 0 else x
        ny = (y - self.margin) / span if span > 0 else y
        return min(max(nx, 0.0), 1.0), min(max(ny, 0.0), 1.0)

    def move(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        """Move the cursor to a normalised (0..1) camera position."""
        nx, ny = self._normalise(x, y)
        with self._lock:
            if self._smoothed is None:
                self._smoothed = (nx, ny)
            else:
                sx, sy = self._smoothed
                a = self.smoothing
                self._smoothed = (sx + a * (nx - sx), sy + a * (ny - sy))
            px, py = self._smoothed

        if not _IS_WINDOWS:
            return None

        import ctypes

        width, height = _screen_size()
        screen_x, screen_y = int(px * (width - 1)), int(py * (height - 1))
        ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
        return screen_x, screen_y

    def click(self) -> bool:
        if not _IS_WINDOWS:
            return False
        import ctypes

        user32 = ctypes.windll.user32
        user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
        user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
        return True

    def reset(self) -> None:
        with self._lock:
            self._smoothed = None
