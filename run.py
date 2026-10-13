"""Entry point for the touchless presentation control dashboard.

Usage:
    python run.py            # start the web dashboard
    python run.py --port 8000
"""
from __future__ import annotations

import argparse
import atexit
import threading
import webbrowser

from app import config
from app.web import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Touchless presentation control")
    parser.add_argument("--host", default=config.WEB_HOST)
    parser.add_argument("--port", type=int, default=config.WEB_PORT)
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app()
    atexit.register(app.session_state.shutdown)  # type: ignore[attr-defined]

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print(f"Touchless Presentation Control running at {url}")
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
