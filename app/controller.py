"""Module 5 - Presentation control.

Maps semantic actions (next slide, scroll, zoom, ...) onto the loaded
document. Holds all mutable session state behind a lock so the tracker
thread and the web layer can share it safely.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import List, Optional

from . import config
from .file_manager import BaseDocument


@dataclass
class ActionEvent:
    action: str
    detail: str
    timestamp: float


@dataclass
class ControllerState:
    index: int = 0
    page_count: int = 0
    title: str = ""
    zoom: float = 1.0
    scroll: float = 0.0
    paused: bool = False
    pointer_enabled: bool = False
    presenting: bool = False
    armed: bool = False
    gesture: str = "NONE"
    tracking_reliable: bool = True
    last_action: str = ""
    revision: int = 0  # bumped whenever the slide view must be re-rendered

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "page_count": self.page_count,
            "title": self.title,
            "zoom": round(self.zoom, 3),
            "scroll": round(self.scroll, 3),
            "paused": self.paused,
            "pointer_enabled": self.pointer_enabled,
            "presenting": self.presenting,
            "armed": self.armed,
            "gesture": self.gesture,
            "tracking_reliable": self.tracking_reliable,
            "last_action": self.last_action,
            "revision": self.revision,
        }


class PresentationController:
    """Owns the presentation state and applies gesture/UI actions."""

    def __init__(self, document: Optional[BaseDocument] = None) -> None:
        self._lock = threading.RLock()
        self._document = document
        self._events: List[ActionEvent] = []
        self.state = ControllerState()
        if document is not None:
            self.load(document)

    # -- document ----------------------------------------------------------
    def load(self, document: BaseDocument) -> None:
        with self._lock:
            self._document = document
            self.state = ControllerState(
                index=0,
                page_count=document.page_count,
                title=document.title,
                armed=True,
            )
            self._events.clear()
            self._log("load", f"{document.title} ({document.page_count} slides)")

    @property
    def document(self) -> Optional[BaseDocument]:
        return self._document

    # -- rendering ---------------------------------------------------------
    def render_current(self):
        with self._lock:
            if self._document is None:
                return None
            return self._document.render(self.state.index)

    # -- actions -----------------------------------------------------------
    def _log(self, action: str, detail: str) -> None:
        import time

        self._events.append(ActionEvent(action, detail, time.time()))
        del self._events[:-60]
        self.state.last_action = action

    def perform(self, action: str, detail: str = "") -> bool:
        """Apply an action, returning True when something changed."""
        handler = getattr(self, f"_action_{action}", None)
        if handler is None:
            return False
        with self._lock:
            changed = bool(handler(detail))
            if changed:
                self._log(action, detail)
                self.state.revision += 1
            return changed

    def _goto(self, index: int) -> bool:
        index = max(0, min(index, self.state.page_count - 1))
        if index == self.state.index:
            return False
        self.state.index = index
        self.state.scroll = 0.0
        self.state.zoom = config.ZOOM_MIN
        return True

    def _action_next_slide(self, detail: str = "") -> bool:
        return self._goto(self.state.index + 1)

    def _action_prev_slide(self, detail: str = "") -> bool:
        return self._goto(self.state.index - 1)

    def _action_scroll_up(self, detail: str = "") -> bool:
        if self.state.scroll <= 0.0:
            return self._goto(self.state.index - 1)
        self.state.scroll = max(0.0, self.state.scroll - config.SCROLL_STEP)
        return True

    def _action_scroll_down(self, detail: str = "") -> bool:
        if self.state.scroll >= 1.0:
            return self._goto(self.state.index + 1)
        self.state.scroll = min(1.0, self.state.scroll + config.SCROLL_STEP)
        return True

    def _action_zoom_in(self, detail: str = "") -> bool:
        new_zoom = min(config.ZOOM_MAX, self.state.zoom * config.ZOOM_STEP)
        if new_zoom == self.state.zoom:
            return False
        self.state.zoom = new_zoom
        return True

    def _action_zoom_out(self, detail: str = "") -> bool:
        new_zoom = max(config.ZOOM_MIN, self.state.zoom / config.ZOOM_STEP)
        if new_zoom == self.state.zoom:
            return False
        self.state.zoom = new_zoom
        return True

    def _action_toggle_pause(self, detail: str = "") -> bool:
        self.state.paused = not self.state.paused
        return True

    def _action_pause(self, detail: str = "") -> bool:
        if self.state.paused:
            return False
        self.state.paused = True
        return True

    def _action_resume(self, detail: str = "") -> bool:
        if not self.state.paused:
            return False
        self.state.paused = False
        return True

    def _action_toggle_pointer(self, detail: str = "") -> bool:
        self.state.pointer_enabled = not self.state.pointer_enabled
        return True

    def _action_toggle_presentation(self, detail: str = "") -> bool:
        self.state.presenting = not self.state.presenting
        return True

    def _action_confirm(self, detail: str = "") -> bool:
        self.state.armed = True
        return True

    def _action_suspend(self, detail: str = "") -> bool:
        return False

    def _action_set_index(self, detail: str = "") -> bool:
        try:
            return self._goto(int(detail))
        except (TypeError, ValueError):
            return False

    # -- queries -----------------------------------------------------------
    def commands_enabled(self) -> bool:
        with self._lock:
            return (
                self._document is not None
                and self.state.armed
                and not self.state.paused
                and self.state.tracking_reliable
            )

    def recent_events(self, limit: int = 20) -> List[dict]:
        with self._lock:
            events = self._events[-limit:]
            return [
                {"action": e.action, "detail": e.detail, "timestamp": e.timestamp}
                for e in reversed(events)
            ]
