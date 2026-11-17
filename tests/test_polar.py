import pytest

from norad.sources.polar import frame_times


def test_frame_times():
    assert frame_times(10.0, 3, 100.0) == pytest.approx([9.98, 9.99, 10.0])


def test_child_crash_reported_not_raised():
    import sys
    import time

    from norad.sources.polar import PolarSource

    src = PolarSource("AA", cmd=[sys.executable, "-c", "import os; os.abort()"])
    src.start()
    time.sleep(1.0)
    st = src.status()
    assert st["connected"] is False
    assert "Bluetooth" in st["error"]


def test_child_status_lines():
    import sys
    import time

    from norad.sources.polar import PolarSource

    code = "import json,time; print(json.dumps({'connected': True, 'count': 130}), flush=True); time.sleep(5)"
    src = PolarSource("AA", cmd=[sys.executable, "-c", code])
    src.start()
    time.sleep(1.0)
    assert src.status()["connected"] is True
    src.stop()


def test_hr_rows_every_report():
    import math

    from norad.sources.polar import hr_rows

    assert hr_rows(10.0, 60, [1000, 1000]) == [(9.0, [60.0, 1000.0]), (10.0, [60.0, 1000.0])]
    (t, (hr, rr)), = hr_rows(10.0, 72, [])  # no beat interval in this report: still show the heart rate
    assert t == 10.0 and hr == 72.0 and math.isnan(rr)
