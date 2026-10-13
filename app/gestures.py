"""Module 4 - Gesture recognition.

Pure, framework-free logic that turns hand/pose landmarks into a discrete
gesture name. Everything here operates on the ``Hand``/``Pose`` containers
from :mod:`app.landmarks`, so it can be unit tested without a camera or
MediaPipe.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Sequence, Tuple

import numpy as np

from . import config
from .landmarks import (
    INDEX_MCP,
    INDEX_PIP,
    INDEX_TIP,
    MIDDLE_PIP,
    MIDDLE_TIP,
    PINKY_PIP,
    PINKY_TIP,
    POSE_LEFT_HIP,
    POSE_LEFT_SHOULDER,
    POSE_RIGHT_HIP,
    POSE_RIGHT_SHOULDER,
    RING_PIP,
    RING_TIP,
    THUMB_MCP,
    THUMB_TIP,
    Hand,
    Pose,
    WRIST,
)

# --- Gesture names --------------------------------------------------------
NONE = "NONE"
NO_HAND = "NO_HAND"
OPEN_PALM = "OPEN_PALM"
FIST = "FIST"
THUMBS_UP = "THUMBS_UP"
TWO_FINGERS = "TWO_FINGERS"
INDEX_ONLY = "INDEX_ONLY"
PINCH = "PINCH"
SPREAD = "SPREAD"
BOTH_HANDS = "BOTH_HANDS"
INDEX_RIGHT = "INDEX_RIGHT"
INDEX_LEFT = "INDEX_LEFT"
INDEX_UP = "INDEX_UP"
INDEX_DOWN = "INDEX_DOWN"

MOTION_GESTURES = {INDEX_RIGHT, INDEX_LEFT, INDEX_UP, INDEX_DOWN}

# Gesture -> presentation action.
GESTURE_ACTIONS = {
    INDEX_RIGHT: "next_slide",
    INDEX_LEFT: "prev_slide",
    INDEX_UP: "scroll_up",
    INDEX_DOWN: "scroll_down",
    OPEN_PALM: "pause",
    FIST: "toggle_pause",
    THUMBS_UP: "confirm",
    TWO_FINGERS: "toggle_pointer",
    PINCH: "zoom_out",
    SPREAD: "zoom_in",
    BOTH_HANDS: "toggle_presentation",
    NO_HAND: "suspend",
}


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))


def hand_scale(hand: Hand) -> float:
    """Reference length of a hand (wrist to middle-finger MCP)."""
    return max(_dist(hand.points[WRIST], hand.points[INDEX_MCP]), 1e-6)


def extended_fingers(hand: Hand) -> Tuple[bool, bool, bool, bool, bool]:
    """Return (thumb, index, middle, ring, pinky) extension flags."""
    p = hand.points
    scale = hand_scale(hand)

    def straight(tip: int, pip: int) -> bool:
        return _dist(p[tip], p[WRIST]) > _dist(p[pip], p[WRIST]) * 1.08

    thumb_ext = (
        _dist(p[THUMB_TIP], p[WRIST]) > _dist(p[THUMB_MCP], p[WRIST]) * 1.05
        and _dist(p[THUMB_TIP], p[INDEX_MCP]) > 0.55 * scale
    )
    return (
        thumb_ext,
        straight(INDEX_TIP, INDEX_PIP),
        straight(MIDDLE_TIP, MIDDLE_PIP),
        straight(RING_TIP, RING_PIP),
        straight(PINKY_TIP, PINKY_PIP),
    )


def pinch_ratio(hand: Hand) -> float:
    """Normalised thumb-tip / index-tip distance (small means pinching)."""
    return _dist(hand.points[THUMB_TIP], hand.points[INDEX_TIP]) / hand_scale(hand)


def is_thumbs_up(hand: Hand) -> bool:
    p = hand.points
    thumb, index, middle, ring, pinky = extended_fingers(hand)
    if not thumb or index or middle or ring or pinky:
        return False
    dy = p[THUMB_TIP][1] - p[THUMB_MCP][1]
    dx = abs(p[THUMB_TIP][0] - p[THUMB_MCP][0])
    return dy < -0.12 and dx < abs(dy) * 0.9


def classify_shape(hand: Hand) -> str:
    """Classify a static hand shape."""
    thumb, index, middle, ring, pinky = extended_fingers(hand)
    fingers = (index, middle, ring, pinky)
    count = sum(fingers)

    if pinch_ratio(hand) < config.PINCH_ON and (index or thumb):
        return PINCH

    if count == 0 and not thumb:
        return FIST

    if is_thumbs_up(hand):
        return THUMBS_UP

    if count == 4 and thumb:
        return OPEN_PALM

    if index and middle and not ring and not pinky:
        return TWO_FINGERS

    if index and not middle and not ring and not pinky:
        return INDEX_ONLY

    return NONE


@dataclass
class MotionTracker:
    """Tracks the index fingertip over time to detect swipes."""

    window: float = config.MOTION_WINDOW
    threshold: float = config.MOTION_THRESHOLD
    idle: float = config.MOTION_IDLE
    history: Deque[Tuple[float, float, float]] = field(default_factory=deque)

    def add(self, x: float, y: float, now: Optional[float] = None) -> None:
        now = time.monotonic() if now is None else now
        self.history.append((now, float(x), float(y)))
        self._trim(now)

    def _trim(self, now: float) -> None:
        while self.history and now - self.history[0][0] > self.window:
            self.history.popleft()

    def reset(self) -> None:
        self.history.clear()

    def displacement(self, now: Optional[float] = None) -> Tuple[float, float]:
        now = time.monotonic() if now is None else now
        self._trim(now)
        if len(self.history) < 2:
            return 0.0, 0.0
        _, x0, y0 = self.history[0]
        _, x1, y1 = self.history[-1]
        return x1 - x0, y1 - y0

    def direction(self, now: Optional[float] = None) -> Optional[str]:
        dx, dy = self.displacement(now)
        if max(abs(dx), abs(dy)) < self.threshold:
            return None
        if abs(dx) >= abs(dy):
            return INDEX_RIGHT if dx > 0 else INDEX_LEFT
        return INDEX_DOWN if dy > 0 else INDEX_UP

    def is_idle(self, now: Optional[float] = None) -> bool:
        dx, dy = self.displacement(now)
        return max(abs(dx), abs(dy)) < self.idle


def both_hands_raised(hands: Sequence[Hand], pose: Optional[Pose]) -> bool:
    """Return True when two hands are visible above the shoulders."""
    if len(hands) < 2:
        return False
    if pose is not None and pose.shoulders_visible():
        shoulder_y = pose.shoulder_center_y()
    else:
        shoulder_y = 0.5
    ys = sorted(float(hand.points[WRIST][1]) for hand in hands)
    return bool(ys[0] < shoulder_y and ys[1] < shoulder_y)


class GestureRecognizer:
    """Stateful recogniser combining shapes, motion and body pose."""

    def __init__(self, num_hands: int = 2) -> None:
        self.num_hands = num_hands
        self.motion = MotionTracker()
        self._pinch_active = False
        self._pinch_reference: Optional[float] = None

    def _pick_hand(self, hands: Sequence[Hand]) -> Hand:
        return max(hands, key=lambda h: h.score)

    def recognize(
        self,
        hands: Sequence[Hand],
        poses: Sequence[Pose] = (),
        now: Optional[float] = None,
    ) -> str:
        """Return the gesture observed in the current frame."""
        now = time.monotonic() if now is None else now
        pose = poses[0] if poses else None

        if len(hands) >= self.num_hands and both_hands_raised(hands, pose):
            self._reset_pinch()
            self.motion.reset()
            return BOTH_HANDS

        if not hands:
            self._reset_pinch()
            self.motion.reset()
            return NO_HAND

        hand = self._pick_hand(hands)
        shape = classify_shape(hand)

        if shape == PINCH:
            ratio = pinch_ratio(hand)
            if not self._pinch_active:
                self._pinch_active = True
                self._pinch_reference = ratio
                self.motion.reset()
                return PINCH
            if self._pinch_reference is not None and ratio - self._pinch_reference > config.SPREAD_STEP:
                self._reset_pinch()
                self.motion.reset()
                return SPREAD
            self.motion.reset()
            return PINCH

        if self._pinch_active:
            # A pinch is in progress but the hand shape changed. A widening
            # thumb/index gap means the user spread the pinched fingers.
            ratio = pinch_ratio(hand)
            spread = (
                self._pinch_reference is not None
                and ratio - self._pinch_reference > config.SPREAD_STEP
            )
            self._reset_pinch()
            self.motion.reset()
            if spread:
                return SPREAD
            return NONE

        if shape == INDEX_ONLY:
            self.motion.add(hand.tip[0], hand.tip[1], now)
            return self.motion.direction(now) or INDEX_ONLY

        self.motion.reset()
        return shape

    def _reset_pinch(self) -> None:
        self._pinch_active = False
        self._pinch_reference = None


def index_tip_position(hands: Sequence[Hand]) -> Optional[Tuple[float, float]]:
    """Return the normalised index tip of the most confident hand."""
    if not hands:
        return None
    hand = max(hands, key=lambda h: h.score)
    tip = hand.tip
    return float(tip[0]), float(tip[1])
