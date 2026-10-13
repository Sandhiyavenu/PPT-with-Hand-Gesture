"""Central configuration for the touchless presentation controller."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
CACHE_DIR = ROOT / ".cache"

HAND_MODEL = MODELS_DIR / "hand_landmarker.task"
POSE_MODEL = MODELS_DIR / "pose_landmarker_lite.task"

SUPPORTED_EXTENSIONS = {".pdf", ".ppt", ".pptx"}
FILE_DIALOG_TYPES = [
    ("Presentations", "*.pdf *.ppt *.pptx"),
    ("PDF document", "*.pdf"),
    ("PowerPoint", "*.ppt *.pptx"),
    ("All files", "*.*"),
]

# --- Web server -----------------------------------------------------------
WEB_HOST = "127.0.0.1"
WEB_PORT = 5000

# --- Camera ---------------------------------------------------------------
CAMERA_INDEX = 0
FRAME_WIDTH = 960
FRAME_HEIGHT = 540
TARGET_FPS = 30

# Backends tried in order. `None` lets OpenCV pick a default. DirectShow is
# preferred on Windows because MSMF often fails with "can't grab frame".
import sys  # noqa: E402

CAMERA_BACKENDS = ["CAP_DSHOW", "CAP_MSMF", None] if sys.platform == "win32" else [None]

# --- Detection thresholds -------------------------------------------------
MIN_HAND_CONFIDENCE = 0.5
MIN_POSE_CONFIDENCE = 0.5
MAX_LANDMARK_ERROR = 0.35
MIN_SHOULDER_VISIBILITY = 0.5

# --- Gesture validation ---------------------------------------------------
STABLE_DURATION = 0.35      # seconds a static gesture must be held
COMMAND_COOLDOWN = 0.70     # seconds before the same gesture may fire again
MOTION_WINDOW = 0.55        # seconds of index-tip history used for direction
MOTION_THRESHOLD = 0.12     # normalised displacement that counts as a swipe
MOTION_IDLE = 0.05          # displacement below which the finger is "neutral"

PINCH_ON = 0.42             # thumb-tip/index-tip distance (normalised) to pinch
PINCH_OFF = 0.60            # release hysteresis
SPREAD_STEP = 0.14          # pinch distance delta that counts as a spread

POINTER_SMOOTHING = 0.45    # exponential smoothing for the virtual pointer
POINTER_MARGIN = 0.15       # ignore outer 15% of the frame for pointer mapping

SLIDE_BASE_WIDTH = 1600     # rendered slide width in pixels
ZOOM_MIN = 1.0
ZOOM_MAX = 5.0
ZOOM_STEP = 1.25
SCROLL_STEP = 0.08          # normalised scroll offset per gesture
