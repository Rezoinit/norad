import math

import pytest

from norad.sources.tobii import FrameBuilder


def eye(eye, ts, gidx, pd=3.2, s=0):
    """The three per-eye packets the glasses send for one frame."""
    return [{"ts": ts, "s": s, "gidx": gidx, "eye": eye, "pc": [1, 2, 3]},
            {"ts": ts, "s": s, "gidx": gidx, "eye": eye, "pd": pd},
            {"ts": ts, "s": s, "gidx": gidx, "eye": eye, "gd": [0.0, 0.0, 1.0]}]


def frame(ts, gidx, pd_l=3.2, pd_r=3.4, s_l=0, s_r=0, s_gp=0):
    return eye("left", ts, gidx, pd_l, s_l) + eye("right", ts, gidx, pd_r, s_r) + [
        {"ts": ts, "s": s_gp, "gidx": gidx, "l": 1, "gp": [0.4, 0.6]},
        {"ts": ts, "s": s_gp, "gidx": gidx, "gp3": [1, 2, 3]}]


def feed(fb, packets):
    gaze, imu = [], []
    for p in packets:
        g, m = fb.add(p)
        gaze += g
        imu += m
    return gaze, imu


def test_every_frame_gets_its_own_pupil():
    fb = FrameBuilder()
    gaze, _ = feed(fb, frame(1000, 1, 3.2, 3.4) + frame(21000, 2, 3.3, 3.5) + frame(41000, 3))
    assert [g[0] for g in gaze] == [1000, 21000]  # a frame is complete when the next one starts
    assert gaze[0][1] == pytest.approx([0.4, 0.6, 3.2, 3.4, 0, 0, 1, 0, 0, 1])
    assert gaze[1][1][2:4] == pytest.approx([3.3, 3.5])


def test_invalid_eye_is_missing_not_repeated():
    fb = FrameBuilder()
    gaze, _ = feed(fb, frame(1000, 1) + frame(21000, 2, s_r=1) + frame(41000, 3))
    assert gaze[1][1][2] == pytest.approx(3.2)
    assert math.isnan(gaze[1][1][3])


def test_blink_frame_is_kept_as_missing_gaze():
    fb = FrameBuilder()
    gaze, _ = feed(fb, frame(1000, 1, s_l=1, s_r=1, s_gp=1) + frame(21000, 2))
    assert len(gaze) == 1 and gaze[0][0] == 1000
    assert all(math.isnan(x) for x in gaze[0][1][:4])


def test_imu_rows():
    fb = FrameBuilder()
    _, imu = feed(fb, [{"ts": 500, "s": 0, "gy": [1, 2, 3]}, {"ts": 510, "s": 0, "ac": [0.1, -9.8, 0.2]}])
    assert imu == [(510, pytest.approx([0.1, -9.8, 0.2, 1, 2, 3]))]


def test_unreachable_glasses_report_error(monkeypatch):
    import time

    import tobiiglassesctrl

    from norad.sources.tobii import TobiiSource

    class FakeController:  # mimics tobiiglassesctrl when the glasses are not reachable
        streaming = False

        def __init__(self, *a, **k):
            pass

        def start_streaming(self):
            pass

        def stop_streaming(self):
            pass

        def get_data(self):
            return {"gp": {"ts": -1}, "mems": {"ac": {"ts": -1}, "gy": {"ts": -1}}}

    monkeypatch.setattr(tobiiglassesctrl, "TobiiGlassesController", FakeController)
    src = TobiiSource("1.2.3.4")
    src.start()
    time.sleep(0.5)
    assert src.running is False
    assert "Tobii" in (src.status()["error"] or "")


class FakeCtrl:
    def __init__(self, result):
        self.result, self.calls = result, []

    def create_project(self, name):
        self.calls.append(("project", name)); return "P"

    def create_participant(self, project_id, name):
        self.calls.append(("participant", project_id, name)); return "U"

    def create_calibration(self, project_id, participant_id):
        self.calls.append(("calibration", project_id, participant_id)); return "C"

    def start_calibration(self, calibration_id):
        self.calls.append(("start", calibration_id))

    def wait_until_calibration_is_done(self, calibration_id):
        return self.result


def test_calibrate_runs_the_tobii_sequence():
    from norad.sources.tobii import TobiiSource

    src = TobiiSource("1.2.3.4")
    src.ctrl = FakeCtrl(True)
    ok, msg = src.calibrate("pilot-01")
    assert ok and "calibrated" in msg.lower()
    assert src.ctrl.calls == [("project", "norad"), ("participant", "P", "pilot-01"),
                              ("calibration", "P", "U"), ("start", "C")]
    src.ctrl = FakeCtrl(False)
    ok, msg = src.calibrate("pilot-01")
    assert not ok and "card" in msg


def test_calibrate_without_glasses():
    from norad.sources.tobii import TobiiSource

    ok, msg = TobiiSource("1.2.3.4").calibrate("p")
    assert not ok and "not connected" in msg.lower()
