"""Modules 4-6 - Tracking loop that ties detection to presentation control.

Runs a background thread that captures frames, detects landmarks,
recognises and validates gestures, applies the resulting presentation
actions and keeps an annotated frame available for the web preview.
"""
from __future__ import annotations

import threading
import time
from typing import List, Optional

import cv2
import numpy as np

from . import config
from .controller import PresentationController
from .gestures import (
    GESTURE_ACTIONS,
    NO_HAND,
    GestureRecognizer,
    index_tip_position,
)
from .landmarks import (
    HAND_CONNECTIONS,
    POSE_CONNECTIONS,
    Hand,
    LandmarkDetector,
    Pose,
)
from .pointer import VirtualPointer
from .validation import GestureValidator
from .webcam import Camera, CameraError

_STATE_COLORS = {
    True: (80, 200, 120),
    False: (80, 80, 220),
}


class Tracker:
    """Background capture + gesture pipeline."""

    def __init__(
        self,
        camera: Camera,
        detector: LandmarkDetector,
        controller: PresentationController,
        pointer: Optional[VirtualPointer] = None,
    ) -> None:
        self.camera = camera
        self.detector = detector
        self.controller = controller
        self.pointer = pointer or VirtualPointer()
        self.recognizer = GestureRecognizer()
        self.validator = GestureValidator()

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._jpeg: Optional[bytes] = None
        self._gesture = "NONE"
        self._error: Optional[str] = None
        self._failures = 0
        self._running = False

    # -- lifecycle ---------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    @property
    def error(self) -> Optional[str]:
        return self._error

    def start(self) -> None:
        if self.running:
            return
        self.camera.open()
        self._stop.clear()
        self._error = None
        self._failures = 0
        self.validator.reset()
        self.pointer.reset()
        self._thread = threading.Thread(target=self._loop, name="tracker", daemon=True)
        self._thread.start()
        self._running = True

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)
        self._thread = None
        # The camera is released by the worker thread in its ``finally`` block
        # so we never release while a frame read is in progress (MSMF hangs).
        if thread is None or not thread.is_alive():
            self.camera.release()
        self.pointer.reset()

    # -- state snapshot ----------------------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            return {"gesture": self._gesture, "error": self._error, "running": self.running}

    def latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._jpeg

    # -- loop --------------------------------------------------------------
    def _loop(self) -> None:
        frame_interval = 1.0 / max(config.TARGET_FPS, 1)
        start = time.monotonic()
        frame_index = 0
        try:
            while not self._stop.is_set():
                loop_start = time.monotonic()
                frame = self.camera.read()
                if frame is None:
                    self._register_failure("Camera frame unavailable.")
                    time.sleep(0.05)
                    continue
                frame_index += 1
                timestamp_ms = int((time.monotonic() - start) * 1000)

                try:
                    hands, poses = self.detector.detect(frame, timestamp_ms)
                    self._failures = 0
                    with self._lock:
                        self._error = None
                    self.controller.state.tracking_reliable = True
                except Exception as exc:  # pragma: no cover - depends on runtime
                    self._register_failure(f"Detection error: {exc}")
                    hands, poses = [], []

                gesture = self.recognizer.recognize(hands, poses)
                self._apply(gesture, hands)
                with self._lock:
                    self._gesture = gesture

                self._publish_frame(frame, hands, poses, gesture)

                elapsed = time.monotonic() - loop_start
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
        except CameraError as exc:
            self._register_failure(str(exc))
        finally:
            self._running = False
            self.camera.release()

    def _register_failure(self, message: str) -> None:
        self._failures += 1
        with self._lock:
            self._error = message
            self.controller.state.tracking_reliable = self._failures < 5
        self.validator.reset()

    def _apply(self, gesture: str, hands: List[Hand]) -> None:
        paused = self.controller.state.paused or not self.controller.state.tracking_reliable
        if not paused:
            fired = self.validator.update(gesture)
            if fired:
                action = GESTURE_ACTIONS.get(fired)
                if action:
                    self.controller.perform(action, fired)
        else:
            self.validator.update(NO_HAND)

        self._update_pointer(hands, gesture)

    def _update_pointer(self, hands: List[Hand], gesture: str) -> None:
        state = self.controller.state
        if not state.pointer_enabled or not hands:
            return
        position = index_tip_position(hands)
        if position is None:
            return
        self.pointer.move(*position)
        if gesture == "PINCH":
            self.pointer.reset()

    # -- drawing -----------------------------------------------------------
    def _publish_frame(
        self, frame: np.ndarray, hands: List[Hand], poses: List[Pose], gesture: str
    ) -> None:
        canvas = frame.copy()
        h, w = canvas.shape[:2]

        for pose in poses:
            points = [
                (int(p[0] * w), int(p[1] * h)) for p in pose.points
            ]
            for a, b in POSE_CONNECTIONS:
                if pose.visibility[a] > 0.4 and pose.visibility[b] > 0.4:
                    cv2.line(canvas, points[a], points[b], (200, 160, 60), 2)
            for i, point in enumerate(points):
                if pose.visibility[i] > 0.4:
                    cv2.circle(canvas, point, 3, (255, 220, 120), -1)

        for hand in hands:
            points = [(int(p[0] * w), int(p[1] * h)) for p in hand.points]
            for a, b in HAND_CONNECTIONS:
                cv2.line(canvas, points[a], points[b], (60, 220, 255), 2)
            for point in points:
                cv2.circle(canvas, point, 3, (255, 255, 255), -1)
            cv2.circle(canvas, points[8], 9, (0, 255, 0), 2)

        state = self.controller.state
        self._draw_banner(canvas, gesture, state)
        ok, buffer = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ok:
            with self._lock:
                self._jpeg = buffer.tobytes()

    def _draw_banner(self, canvas: np.ndarray, gesture: str, state) -> None:
        h, w = canvas.shape[:2]
        cv2.rectangle(canvas, (0, 0), (w, 46), (20, 20, 20), -1)
        cv2.putText(
            canvas, f"GESTURE: {gesture}", (12, 31),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (120, 255, 160), 2,
        )
        status = "PAUSED" if state.paused else "ACTIVE"
        color = _STATE_COLORS[state.paused]
        cv2.putText(
            canvas, status, (w - 150, 31),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2,
        )
