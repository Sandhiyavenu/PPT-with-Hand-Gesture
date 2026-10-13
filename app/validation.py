"""Module 6 (part) - Gesture validation.

Guards the presentation actions so a command only fires once the gesture is
deliberate and stable, only once per gesture, and never during the cooldown
window. This is where the "trigger once per gesture until neutral" rule lives.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Set

from . import config
from .gestures import MOTION_GESTURES, NONE, NO_HAND


@dataclass
class ValidationConfig:
    stable_duration: float = config.STABLE_DURATION
    cooldown: float = config.COMMAND_COOLDOWN
    require_neutral: bool = True


class GestureValidator:
    """Convert a stream of observed gestures into discrete fired commands."""

    def __init__(self, config_: Optional[ValidationConfig] = None) -> None:
        self.config = config_ or ValidationConfig()
        self._current: Optional[str] = None
        self._current_since = 0.0
        self._last_fire: dict[str, float] = {}
        # Gestures already fired that must wait for a neutral pose before
        # they may fire again ("trigger once per gesture until neutral").
        self._latched: Set[str] = set()

    def reset(self) -> None:
        self._current = None
        self._current_since = 0.0
        self._last_fire.clear()
        self._latched.clear()

    @staticmethod
    def _is_neutral(gesture: Optional[str]) -> bool:
        return gesture in (None, NONE, NO_HAND)

    def _stable_enough(self, gesture: str, now: float) -> bool:
        if gesture in MOTION_GESTURES:
            return True  # swipes are events, not poses to hold
        return (now - self._current_since) >= self.config.stable_duration

    def _cooldown_ok(self, gesture: str, now: float) -> bool:
        last = self._last_fire.get(gesture)
        return last is None or (now - last) >= self.config.cooldown

    def update(self, gesture: Optional[str], now: Optional[float] = None) -> Optional[str]:
        """Feed an observed gesture; return the gesture name if it should fire."""
        now = time.monotonic() if now is None else now

        if gesture != self._current:
            self._current = gesture
            self._current_since = now

        if self._is_neutral(gesture):
            self._latched.clear()
            return None

        assert gesture is not None
        if self.config.require_neutral and gesture in self._latched:
            return None
        if not self._stable_enough(gesture, now):
            return None
        if not self._cooldown_ok(gesture, now):
            return None

        self._last_fire[gesture] = now
        self._latched.add(gesture)
        return gesture
