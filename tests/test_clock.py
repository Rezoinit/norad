import numpy as np

from norad.clock import ClockMap

rng = np.random.default_rng(0)


def test_constant_delay_with_jitter():
    cm = ClockMap()
    for k in range(3000):
        dev = k * 0.01
        arrival = dev + 100.0 + 0.005 + rng.uniform(0, 0.040)
        mapped = cm.map(dev, arrival)
        if k >= 100:
            assert abs(mapped - (dev + 100.005)) < 0.002


def test_reset_after_device_restart():
    cm = ClockMap()
    for k in range(500):
        cm.map(k * 0.01, k * 0.01 + 100.005 + rng.uniform(0, 0.04))
    cm.reset()
    mapped = cm.map(0.0, 0.0 + 200.005 + rng.uniform(0, 0.04))
    assert abs(mapped - 200.0) < 0.05


def test_drift():
    cm = ClockMap()
    for k in range(60000):
        dev = k * 0.01
        true = dev * (1 + 50e-6) + 100.005
        mapped = cm.map(dev, true + rng.uniform(0, 0.040))
        if k >= 100:
            assert abs(mapped - true) < 0.003
