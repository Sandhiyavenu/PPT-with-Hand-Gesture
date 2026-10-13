# PPT with Hand Gesture

Touchless presentation control. Control a PowerPoint/PDF deck with hand gestures
in front of your webcam, monitored through a local web dashboard.

Built with Python, OpenCV, MediaPipe (hand + pose landmarkers), and Flask.

## Features

- Control a running presentation hands-free using webcam gesture recognition.
- Load PDF, PPT and PPTX decks (rendered to images via `python-pptx` / `PyMuPDF`).
- Live annotated webcam preview (MJPEG stream) in the browser.
- Manual controls (next/prev/zoom/scroll/pause) from the dashboard.
- Virtual pointer that follows your index fingertip.
- Gesture validation (hold time + cooldown) to avoid accidental triggers.
- Runs entirely locally — nothing leaves your machine.

## Requirements

- Python 3.10+
- A webcam
- Windows recommended (uses DirectShow backend automatically)

Install dependencies:

```bash
pip install -r requirements.txt
```

The MediaPipe model bundles (`.task` files) are already present in `models/`:

- `hand_landmarker.task`
- `pose_landmarker_lite.task`
- `pose_landmarker_full.task`

## Quick start

```bash
python run.py
```

This starts the dashboard at `http://127.0.0.1:5000/` and opens your browser.

Optional arguments:

```bash
python run.py --port 8000     # different port
python run.py --no-browser    # don't auto-open the browser
```

1. Open the dashboard and upload your deck.
2. Press **Start session**.
3. Stand in front of the camera and use the gestures below.

## Gesture controls

| Gesture | Action |
| --- | --- |
| Index finger swipe **right** | Next slide |
| Index finger swipe **left** | Previous slide |
| Index finger swipe **up** | Scroll up |
| Index finger swipe **down** | Scroll down |
| Open palm | Pause |
| Fist | Toggle pause |
| Thumbs up | Confirm |
| Two fingers (Victory) | Toggle virtual pointer |
| Pinch | Zoom out |
| Spread (open pinch) | Zoom in |
| Both hands raised | Toggle fullscreen presentation |

## Configuration

All knobs live in `app/config.py`:

- Camera index/resolution/fps and backend order
- Gesture thresholds (confidence, pinch, swipe displacement)
- Validation timing (stable duration, command cooldown)
- Slider/zoom/scroll behaviour

## Web API

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/upload` | Upload a deck (PDF/PPT/PPTX) |
| `POST` | `/api/session/start` | Start the tracking session |
| `POST` | `/api/session/stop` | Stop the tracking session |
| `POST` | `/api/action/<name>` | Trigger an action manually |
| `GET` | `/api/status` | Current state (slide index, zoom, running, ...) |
| `GET` | `/api/slide/<index>` | JPEG of a rendered slide |
| `GET` | `/api/video` | MJPEG annotated camera stream |

Manual actions: `next`, `prev`, `scroll_up`, `scroll_down`, `zoom_in`,
`zoom_out`, `toggle_pause`, `toggle_pointer`, `toggle_presentation`, `confirm`.

## Tests

```bash
python -m pytest
```

## Project structure

```
app/
  config.py        central configuration
  webcam.py        camera wrapper (DirectShow/MSMF backend fallback)
  landmarks.py     MediaPipe hand/pose landmark detection
  gestures.py      gesture recognition logic
  validation.py    hold-time and cooldown validation
  controller.py    presentation state machine
  pointer.py       virtual pointer smoothing
  file_manager.py  deck loading + rendering (PDF/PPT/PPTX)
  session.py       session lifecycle (tracker thread, state)
  tracker.py       background capture + gesture pipeline
  web/             Flask dashboard (routes, templates, static assets)
models/            MediaPipe .task model bundles
tests/             pytest suite
run.py             entry point
```