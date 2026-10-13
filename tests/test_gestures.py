import numpy as np

from app import gestures
from app.landmarks import Hand, Pose
from tests.hand_factory import make_hand


def hand(**kwargs) -> Hand:
    return Hand(points=make_hand(**kwargs))


def test_open_palm_extended_fingers():
    palm = hand(index=True, middle=True, ring=True, pinky=True, thumb=True)
    assert gestures.extended_fingers(palm) == (True, True, True, True, True)
    assert gestures.classify_shape(palm) == gestures.OPEN_PALM


def test_fist_and_open_palm_are_distinct():
    fist = hand()
    assert gestures.classify_shape(fist) == gestures.FIST


def test_thumbs_up():
    assert gestures.classify_shape(hand(thumb_up=True)) == gestures.THUMBS_UP


def test_two_fingers_and_index_only():
    assert gestures.classify_shape(hand(index=True, middle=True)) == gestures.TWO_FINGERS
    assert gestures.classify_shape(hand(index=True)) == gestures.INDEX_ONLY


def test_pinch_and_spread():
    pinched = hand(index=True, pinch=True)
    assert gestures.classify_shape(pinched) == gestures.PINCH

    recognizer = gestures.GestureRecognizer()
    assert recognizer.recognize([pinched], now=0.0) == gestures.PINCH

    released = hand(index=True, thumb=True, pinch=True)
    released.points[4] = [0.30, 0.56, 0.0]  # move thumb tip away
    assert recognizer.recognize([released], now=0.1) == gestures.SPREAD


def test_no_hand_and_both_hands():
    recognizer = gestures.GestureRecognizer()
    assert recognizer.recognize([]) == gestures.NO_HAND

    raised = [
        Hand(points=make_hand(index=True)),
        Hand(points=make_hand(index=True)),
    ]
    for h in raised:
        h.points[0][1] = 0.30  # wrists above the default shoulder line
    assert recognizer.recognize(raised) == gestures.BOTH_HANDS


def test_both_hands_raised_uses_pose_shoulders():
    low = Hand(points=make_hand(index=True))
    low.points[0][1] = 0.55
    high = Hand(points=make_hand(index=True))
    high.points[0][1] = 0.40

    pose_points = np.zeros((33, 3))
    pose_points[11] = [0.4, 0.45, 0.0]
    pose_points[12] = [0.6, 0.45, 0.0]
    pose_points[23] = [0.4, 0.8, 0.0]
    pose_points[24] = [0.6, 0.8, 0.0]
    visibility = np.ones(33)
    pose = Pose(points=pose_points, visibility=visibility)

    assert gestures.both_hands_raised([high, high], pose) is True
    assert gestures.both_hands_raised([low, low], pose) is False


def test_index_motion_directions():
    def track(dx, dy):
        recognizer = gestures.GestureRecognizer()
        first = Hand(points=make_hand(index=True))
        recognizer.recognize([first], now=0.0)
        second = Hand(points=make_hand(index=True))
        second.points[:, 0] += dx
        second.points[:, 1] += dy
        return recognizer.recognize([second], now=0.3)

    assert track(0.30, 0.0) == gestures.INDEX_RIGHT
    assert track(-0.30, 0.0) == gestures.INDEX_LEFT
    assert track(0.0, -0.30) == gestures.INDEX_UP
    assert track(0.0, 0.30) == gestures.INDEX_DOWN
    assert track(0.01, 0.01) == gestures.INDEX_ONLY


def test_motion_tracker_reset():
    tracker = gestures.MotionTracker()
    tracker.add(0.2, 0.2, now=0.0)
    tracker.add(0.8, 0.2, now=0.1)
    assert tracker.direction(now=0.1) == gestures.INDEX_RIGHT
    tracker.reset()
    assert tracker.direction(now=0.1) is None
