from app import gestures
from app.validation import GestureValidator, ValidationConfig


def make_validator() -> GestureValidator:
    return GestureValidator(ValidationConfig(stable_duration=0.35, cooldown=0.70))


def test_static_gesture_requires_stability():
    validator = make_validator()
    assert validator.update(gestures.OPEN_PALM, now=0.0) is None
    assert validator.update(gestures.OPEN_PALM, now=0.2) is None
    assert validator.update(gestures.OPEN_PALM, now=0.4) == gestures.OPEN_PALM


def test_fires_once_until_neutral():
    validator = make_validator()
    assert validator.update(gestures.FIST, now=0.0) is None
    assert validator.update(gestures.FIST, now=0.5) == gestures.FIST
    assert validator.update(gestures.FIST, now=1.0) is None  # latched
    assert validator.update(gestures.NONE, now=1.1) is None
    assert validator.update(gestures.FIST, now=1.2) is None
    assert validator.update(gestures.FIST, now=1.6) == gestures.FIST


def test_cooldown_blocks_rapid_repeat():
    validator = make_validator()
    first = validator.update(gestures.INDEX_RIGHT, now=0.0)
    assert first == gestures.INDEX_RIGHT
    validator.update(gestures.NO_HAND, now=0.1)
    assert validator.update(gestures.INDEX_RIGHT, now=0.2) is None  # cooldown
    assert validator.update(gestures.INDEX_RIGHT, now=0.8) == gestures.INDEX_RIGHT


def test_motion_gesture_fires_immediately():
    validator = make_validator()
    assert validator.update(gestures.INDEX_LEFT, now=5.0) == gestures.INDEX_LEFT


def test_no_hand_is_neutral():
    validator = make_validator()
    assert validator.update(gestures.NO_HAND, now=0.0) is None
    assert validator.update(gestures.NO_HAND, now=10.0) is None
