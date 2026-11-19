import numpy as np
import pytest

from norad.live import rms_envelope


def test_rms_envelope():
    fs = 200.0
    t = np.arange(0, 2, 1 / fs)
    x = 2000 + 2 * np.sin(2 * np.pi * 50 * t)  # offset must not matter
    env = rms_envelope(x, fs, 0.1)
    assert len(env) == len(x)
    assert np.median(env) == pytest.approx(np.sqrt(2), abs=0.05)


def test_nasal_envelope_in_mv():
    from norad.live import LiveHub, MV_PER_COUNT

    fs = 800.0
    t = np.arange(0, 1, 1 / fs)
    x = 2825 + 100 * np.sin(2 * np.pi * 50 * t)  # counts: rest level plus a 100-count tone
    env, _ = LiveHub(None)._nasal_envelope([[0, 0, v, v, 0] for v in x], list(t))
    assert MV_PER_COUNT == pytest.approx(0.586, abs=0.001)
    assert np.median(np.array(env)[:, 0]) == pytest.approx(100 / np.sqrt(2) * MV_PER_COUNT, rel=0.05)


def test_rmssd_drops_bad_beats():
    from norad.live import clean_beats, rmssd

    rr = np.array([800, 820] * 30, dtype=float)  # successive differences all 20 ms
    assert rmssd(rr) == pytest.approx(20.0)
    rr[10] = 1600  # one missed beat
    assert not clean_beats(rr)[10]
    assert rmssd(rr) == pytest.approx(20.0)
    assert np.isnan(rmssd(np.array([800, 800, 1600] * 20, dtype=float)))  # 1 in 3 bad: no value


def test_hrv_waits_for_60_s():
    from norad.live import LiveHub

    hub = LiveHub(None)
    rows, ts = hub._hrv([[70, 800 + 20 * (k % 2)] for k in range(50)], [0.8 * k for k in range(50)])
    assert rows == []  # 40 s of beats: too short
    rows, ts = hub._hrv([[70, 800 + 20 * (k % 2)] for k in range(50, 100)], [0.8 * k for k in range(50, 100)])
    assert rows and rows[-1] == [20.0] and ts[-1] == pytest.approx(79.2)


def test_emitted_payload_has_no_nan():
    import json
    import time

    from norad.live import LiveHub
    from norad.lsl_io import make_outlet

    class FakeSio:
        def __init__(self):
            self.sent = []

        def emit(self, event, data):
            self.sent.append(json.dumps(data))

    out = make_outlet("norad_test_nan", ["a", "b"], 50)
    hub = LiveHub(FakeSio())
    deadline = time.time() + 3
    while "norad_test_nan" not in hub.inlets and time.time() < deadline:
        hub._resolve()
    hub.inlets["norad_test_nan"].open_stream(timeout=2)
    out.push_sample([1.0, float("nan")])
    time.sleep(0.3)
    hub._tick()
    sent = [s for s in hub.sio.sent if "norad_test_nan" in s]
    assert sent and all("NaN" not in s for s in sent)
