"""Module 3 - Landmark detection.

Uses the MediaPipe Tasks API (Hands + Pose) to extract hand and body
landmarks from a frame. Landmarks are returned as simple numpy arrays so the
gesture layer stays free of MediaPipe types and remains unit testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from . import config

# MediaPipe hand landmark indices.
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

# MediaPipe pose landmark indices.
POSE_NOSE = 0
POSE_LEFT_SHOULDER, POSE_RIGHT_SHOULDER = 11, 12
POSE_LEFT_ELBOW, POSE_RIGHT_ELBOW = 13, 14
POSE_LEFT_WRIST, POSE_RIGHT_WRIST = 15, 16
POSE_LEFT_HIP, POSE_RIGHT_HIP = 23, 24

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]

POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
]


@dataclass
class Hand:
    """A single detected hand."""

    points: np.ndarray          # shape (21, 3), normalised x/y/z
    handedness: str = "Unknown"
    score: float = 1.0

    @property
    def tip(self) -> np.ndarray:
        return self.points[INDEX_TIP]

    @property
    def wrist(self) -> np.ndarray:
        return self.points[WRIST]


@dataclass
class Pose:
    """A single detected body pose."""

    points: np.ndarray          # shape (33, 3)
    visibility: np.ndarray      # shape (33,)
    score: float = 1.0

    def shoulder_center_y(self) -> float:
        return float((self.points[POSE_LEFT_SHOULDER][1] + self.points[POSE_RIGHT_SHOULDER][1]) / 2)

    def hip_center_y(self) -> float:
        return float((self.points[POSE_LEFT_HIP][1] + self.points[POSE_RIGHT_HIP][1]) / 2)

    def shoulders_visible(self) -> bool:
        return bool(
            self.visibility[POSE_LEFT_SHOULDER] >= config.MIN_SHOULDER_VISIBILITY
            and self.visibility[POSE_RIGHT_SHOULDER] >= config.MIN_SHOULDER_VISIBILITY
        )


class LandmarkDetector:
    """Wraps MediaPipe HandLandmarker and PoseLandmarker."""

    def __init__(
        self,
        hand_model: str = str(config.HAND_MODEL),
        pose_model: str = str(config.POSE_MODEL),
        num_hands: int = 2,
    ) -> None:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        self._timestamp_ms = 0
        self.reliable = True

        hand_options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=hand_model),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=config.MIN_HAND_CONFIDENCE,
            min_hand_presence_confidence=config.MIN_HAND_CONFIDENCE,
            min_tracking_confidence=config.MIN_HAND_CONFIDENCE,
        )
        self._hands = vision.HandLandmarker.create_from_options(hand_options)

        pose_options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=pose_model),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=config.MIN_POSE_CONFIDENCE,
            min_pose_presence_confidence=config.MIN_POSE_CONFIDENCE,
            min_tracking_confidence=config.MIN_POSE_CONFIDENCE,
        )
        self._pose = vision.PoseLandmarker.create_from_options(pose_options)

    def detect(self, frame_bgr: np.ndarray, timestamp_ms: int) -> Tuple[List[Hand], List[Pose]]:
        """Detect hands and poses in a BGR frame."""
        import cv2

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = max(int(timestamp_ms), self._timestamp_ms + 1)
        self._timestamp_ms = timestamp_ms

        hands: List[Hand] = []
        poses: List[Pose] = []

        hand_result = self._hands.detect_for_video(mp_image, timestamp_ms)
        for landmarks, handedness in zip(hand_result.hand_landmarks, hand_result.handedness):
            points = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=float)
            label = handedness[0].category_name if handedness else "Unknown"
            score = float(handedness[0].score) if handedness else 1.0
            hands.append(Hand(points=points, handedness=label, score=score))

        pose_result = self._pose.detect_for_video(mp_image, timestamp_ms)
        for landmarks in pose_result.pose_landmarks:
            points = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=float)
            visibility = np.array([getattr(lm, "visibility", 1.0) for lm in landmarks], dtype=float)
            poses.append(Pose(points=points, visibility=visibility))

        return hands, poses

    def close(self) -> None:
        for landmarker in (self._hands, self._pose):
            close = getattr(landmarker, "close", None)
            if callable(close):
                close()
