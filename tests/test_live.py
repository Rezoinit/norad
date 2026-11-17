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
