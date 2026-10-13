"""Module 2 - Webcam management.

Wraps OpenCV's VideoCapture and exposes a small, testable interface for the
rest of the application. Frames are mirrored so that user motion maps
naturally to on-screen motion.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from . import config


class CameraError(Exception):
    pass


class Camera:
    """Thin wrapper around cv2.VideoCapture."""

    def __init__(
        self,
        index: int = config.CAMERA_INDEX,
        width: int = config.FRAME_WIDTH,
        height: int = config.FRAME_HEIGHT,
    ) -> None:
        self.index = index
        self.width = width
        self.height = height
        self._capture = None

    @property
    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    @staticmethod
    def available() -> bool:
        """Check whether a camera can be opened without keeping it open."""
        import cv2

        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        ok = cap.isOpened()
        cap.release()
        return ok

    def open(self) -> None:
        import cv2

        if self.is_open:
            return
        self._capture = self._open_capture(cv2)
        if self._capture is None:
            raise CameraError(
                f"Cannot open camera {self.index}. It may be in use by another app."
            )
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

    def _open_capture(self, cv2):
        """Try each backend in turn until a camera opens successfully.

        Windows' default MSMF backend frequently fails to grab frames
        (``can't grab frame. Error: -1072875772``); DirectShow is more
        reliable, so it is preferred there.
        """
        backends = config.CAMERA_BACKENDS or [None]
        for backend in backends:
            backend_flag = getattr(cv2, backend) if isinstance(backend, str) else backend
            capture = (
                cv2.VideoCapture(self.index, backend_flag)
                if backend_flag is not None
                else cv2.VideoCapture(self.index)
            )
            if capture.isOpened():
                return capture
            capture.release()
        return None

    def read(self) -> Optional[np.ndarray]:
        """Return a mirrored BGR frame, or None when the frame is unavailable."""
        if not self.is_open:
            return None
        ok, frame = self._capture.read()
        if not ok or frame is None:
            return None
        import cv2

        frame = cv2.flip(frame, 1)
        return frame

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.release()
