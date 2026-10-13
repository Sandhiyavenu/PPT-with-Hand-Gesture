"""HTTP routes for the dashboard and the JSON/MJPEG APIs."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
)

from ..controller import PresentationController
from ..gestures import GESTURE_ACTIONS
from ..file_manager import PresentationError
from ..session import Session, SessionError

bp = Blueprint("dashboard", __name__)

_MANUAL_ACTIONS = {
    "next": "next_slide",
    "prev": "prev_slide",
    "scroll_up": "scroll_up",
    "scroll_down": "scroll_down",
    "zoom_in": "zoom_in",
    "zoom_out": "zoom_out",
    "toggle_pause": "toggle_pause",
    "toggle_pointer": "toggle_pointer",
    "toggle_presentation": "toggle_presentation",
    "confirm": "confirm",
}

def _session() -> Session:
    return current_app.session_state  # type: ignore[attr-defined]


@bp.get("/")
def index():
    return render_template("index.html", gesture_map=GESTURE_ACTIONS)


@bp.get("/api/status")
def status():
    return jsonify(_session().status())


@bp.post("/api/upload")
def upload():
    session = _session()
    upload_file = request.files.get("file")
    if upload_file is None or upload_file.filename == "":
        return jsonify({"error": "No file uploaded."}), 400

    suffix = Path(upload_file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        upload_file.save(handle)
        temp_path = handle.name

    try:
        info = session.upload(temp_path)
    except (SessionError, PresentationError) as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass

    info["message"] = session.message
    return jsonify(info)


@bp.post("/api/session/start")
def start_session():
    try:
        _session().start()
    except SessionError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_session().status())


@bp.post("/api/session/stop")
def stop_session():
    _session().stop()
    return jsonify(_session().status())


@bp.post("/api/action/<name>")
def manual_action(name: str):
    action = _MANUAL_ACTIONS.get(name)
    if action is None:
        abort(404)
    controller: PresentationController = _session().controller
    controller.perform(action, "manual")
    return jsonify(_session().status())


@bp.get("/api/slide")
@bp.get("/api/slide/<int:index>")
def slide(index: int | None = None):
    try:
        payload = _session().slide_png(index)
    except SessionError as exc:
        return jsonify({"error": str(exc)}), 404
    response = send_file(
        _bytes_io(payload),
        mimetype="image/jpeg",
        max_age=0,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/api/video")
def video():
    session = _session()

    def generate():
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        while True:
            tracker = getattr(session, "_tracker", None)
            jpeg = tracker.latest_jpeg() if tracker is not None else None
            if jpeg:
                yield boundary + jpeg + b"\r\n"
            time.sleep(1.0 / 25)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


def _bytes_io(payload: bytes):
    import io

    return io.BytesIO(payload)
