"""Application session.

Holds the single active presentation session (document, camera, detector,
tracker) and exposes a small API used by the Flask routes. Keeping this
stateful object separate from the web layer makes the app easy to test and
keeps camera/detector lifetimes explicit.
"""
from __future__ import annotations

import io
import threading
from typing import Optional

from . import config
from .controller import PresentationController
from .file_manager import BaseDocument, PresentationError, load_document
from .tracker import Tracker
from .webcam import Camera, CameraError


class SessionError(Exception):
    pass


class Session:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.controller = PresentationController()
        self.camera = Camera()
        self._detector = None
        self._tracker: Optional[Tracker] = None
        self._document: Optional[BaseDocument] = None
        self._slide_cache: dict[int, bytes] = {}
        self._message = "Ready."

    # -- properties --------------------------------------------------------
    @property
    def document(self) -> Optional[BaseDocument]:
        return self._document

    @property
    def message(self) -> str:
        return self._message

    @property
    def running(self) -> bool:
        return self._tracker is not None and self._tracker.running

    # -- file management (Module 1) ----------------------------------------
    def upload(self, path: str, progress=None) -> dict:
        with self._lock:
            if self.running:
                self.stop()
            try:
                document = load_document(path, progress=progress)
            except PresentationError as exc:
                self._message = str(exc)
                raise SessionError(str(exc)) from exc

            self._document = document
            self.controller.load(document)
            self._slide_cache.clear()
            self._message = f"Loaded {document.title} ({document.page_count} slides)."
            return {
                "title": document.title,
                "kind": document.kind,
                "page_count": document.page_count,
            }

    # -- camera / tracker (Modules 2-6) ------------------------------------
    def start(self) -> None:
        with self._lock:
            if self._document is None:
                raise SessionError("Upload a presentation before starting.")
            if self.running:
                return
            if self._detector is None:
                from .landmarks import LandmarkDetector

                try:
                    self._detector = LandmarkDetector()
                except Exception as exc:  # pragma: no cover - model/runtime issue
                    self._message = f"Could not load MediaPipe models: {exc}"
                    raise SessionError(self._message) from exc

            if self._tracker is None or self._tracker.detector is not self._detector:
                self._tracker = Tracker(self.camera, self._detector, self.controller)
            try:
                self._tracker.start()
            except CameraError as exc:
                self._message = str(exc)
                raise SessionError(str(exc)) from exc
            self.controller.state.tracking_reliable = True
            self.controller.state.armed = True
            self._message = "Tracking started."

    def stop(self) -> None:
        with self._lock:
            if self._tracker is not None:
                self._tracker.stop()
            self.camera.release()
            self._slide_cache.clear()
            self._message = "Stopped. Webcam released."

    def shutdown(self) -> None:
        with self._lock:
            if self._tracker is not None:
                self._tracker.stop()
            if self._detector is not None:
                self._detector.close()
                self._detector = None
            if self._document is not None:
                self._document.close()
                self._document = None
            self._slide_cache.clear()

    # -- slide rendering ---------------------------------------------------
    def slide_png(self, index: Optional[int] = None) -> bytes:
        with self._lock:
            document = self._document
            if document is None:
                raise SessionError("No presentation loaded.")
            if index is None:
                index = self.controller.state.index
            index = max(0, min(index, document.page_count - 1))
            if index not in self._slide_cache:
                image = document.render(index)
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=88)
                self._slide_cache[index] = buffer.getvalue()
            return self._slide_cache[index]

    # -- status ------------------------------------------------------------
    def status(self) -> dict:
        with self._lock:
            state = self.controller.state.as_dict()
            tracker = self._tracker.snapshot() if self._tracker is not None else None
            if tracker:
                state["gesture"] = tracker["gesture"]
                state["tracker_error"] = tracker["error"]
            return {
                **state,
                "running": self.running,
                "message": self._message,
                "events": self.controller.recent_events(limit=12),
            }
