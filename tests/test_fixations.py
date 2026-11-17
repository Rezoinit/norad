import math

import pytest

from norad.live import FixationDetector, gaze_direction

NAN = float("nan")


def rot(deg):
    a = math.radians(deg)
    return [math.sin(a), 0.0, math.cos(a)]


def test_steady_gaze_is_a_fixation():
    fd = FixationDetector()
    for k in range(50):  # 1 s at 50 Hz
        vel, in_fix, dur, per_min = fd.update(k * 0.02, rot(0))
    assert in_fix and vel == pytest.approx(0, abs=1e-6)
    assert dur == pytest.approx(0.98, abs=0.03)


def test_saccade_ends_fixation_and_counts_it():
    fd = FixationDetector()
    for k in range(50):
        fd.update(k * 0.02, rot(0))
    vel, in_fix, dur, per_min = fd.update(1.0, rot(10))  # 10 deg in 20 ms = 500 deg/s
    assert vel == pytest.approx(500, rel=0.01)
    assert not in_fix and dur == 0
    assert per_min == 1


def test_too_short_is_not_a_fixation():
    fd = FixationDetector()  # minimum 60 ms
    fd.update(0.00, rot(0))
    vel, in_fix, dur, _ = fd.update(0.04, rot(0.1))  # 40 ms below threshold
    assert not in_fix


def test_lost_eye_breaks_fixation():
    fd = FixationDetector()
    for k in range(10):
        fd.update(k * 0.02, rot(0))
    vel, in_fix, dur, _ = fd.update(0.2, None)
    assert math.isnan(vel) and not in_fix


def test_gaze_direction_uses_available_eyes():
    assert gaze_direction([0, 0, 1], [NAN, NAN, NAN]) == pytest.approx([0, 0, 1])
    assert gaze_direction([NAN] * 3, [NAN] * 3) is None
    assert gaze_direction(rot(10), rot(-10)) == pytest.approx([0, 0, 1])


def test_livehub_fixation_rows():
    from norad.live import LiveHub

    hub = LiveHub(sio=None)
    row = [0, 0.5, 0.5, 3.0, 3.1, *rot(0), *rot(0)]  # norad_tobii columns
    rows, ts = hub._fixations([row] * 10, [k * 0.02 for k in range(10)])
    assert ts == [k * 0.02 for k in range(10)]
    vel, in_fix, dur, per_min = rows[-1]
    assert in_fix == 1 and dur == pytest.approx(0.18)
