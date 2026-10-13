"""Flask application factory for the touchless presentation dashboard."""
from __future__ import annotations

from flask import Flask

from .routes import bp
from ..session import Session


def create_app(session: Session | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024 * 1024
    app.session_state = session or Session()  # type: ignore[attr-defined]
    app.register_blueprint(bp)
    return app


__all__ = ["create_app"]
