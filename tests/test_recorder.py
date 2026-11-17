import csv
import json
import time
from datetime import datetime

from norad.lsl_io import make_outlet
from norad.recorder import Recorder, folder_name


def test_folder_name():
    assert folder_name(datetime(2026, 11, 17, 9, 5), "Pilot 01", "Mental Math!") == \
        "2026-11-17_0905_pilot-01_mental-math"
    assert folder_name(datetime(2026, 11, 17, 9, 5), "", "") == "2026-11-17_0905_none_none"


def test_record_roundtrip(tmp_path):
    out = make_outlet("norad_test_rec", ["a"], 100)
    rec = Recorder(tmp_path)
    folder = rec.start("p", "t")
    assert "norad_test_rec" in rec.streams
    for k in range(50):
        out.push_sample([float(k)])
        time.sleep(0.01)
    rec.stop()
    rows = list(csv.reader(open(folder / "raw" / "test_rec.csv")))
    assert rows[0] == ["t_lsl", "a"]
    assert len(rows) == 51
    meta = json.loads((folder / "session.json").read_text())
    assert meta["schema_version"] == 1
    assert meta["samples"]["norad_test_rec"] == 50
    assert meta["participant"] == "p" and meta["task"] == "t"


def test_note_updates_extra(tmp_path):
    rec = Recorder(tmp_path)
    folder = rec.start("p", "t", extra={"a": 1})
    rec.note(xdf=False)
    rec.stop()
    assert json.loads((folder / "session.json").read_text())["extra"] == {"a": 1, "xdf": False}


def test_stop_with_continuous_stream(tmp_path):
    import threading

    out = make_outlet("norad_test_cont", ["a"], 200)
    running = True

    def push():
        while running:
            out.push_sample([1.0])
            time.sleep(0.005)

    threading.Thread(target=push, daemon=True).start()
    rec = Recorder(tmp_path)
    folder = rec.start("p", "t")
    time.sleep(0.5)
    t0 = time.monotonic()
    rec.stop()
    assert time.monotonic() - t0 < 2.0
    path = folder / "raw" / "test_cont.csv"
    n = len(path.read_text().splitlines())
    time.sleep(0.5)
    assert len(path.read_text().splitlines()) == n  # nothing written after stop
    stop_lsl = json.loads((folder / "session.json").read_text())["stop_lsl"]
    assert all(float(r.split(",")[0]) <= stop_lsl for r in path.read_text().splitlines()[1:])
    running = False


def test_double_start_makes_one_folder(tmp_path):
    import threading

    rec = Recorder(tmp_path)
    errors = []

    def go():
        try:
            rec.start("p", "t")
        except RuntimeError as e:
            errors.append(e)

    threads = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    rec.stop()
    assert len(list(tmp_path.iterdir())) == 1
    assert len(errors) == 1


def test_stop_keeps_late_frames(tmp_path):
    """H10-style frames arrive ~0.56 s apart, back-dated; samples before Stop must be kept."""
    import threading

    import pylsl

    out = make_outlet("norad_test_frames", ["a"], 130)
    running = True

    def push():
        while running:
            now = pylsl.local_clock()
            for i in range(73):
                out.push_sample([1.0], now - (72 - i) / 130)
            time.sleep(0.56)

    rec = Recorder(tmp_path)
    folder = rec.start("p", "t")
    threading.Thread(target=push, daemon=True).start()
    time.sleep(1.5)
    rec.stop()
    running = False
    stop_lsl = json.loads((folder / "session.json").read_text())["stop_lsl"]
    ts = [float(r.split(",")[0]) for r in (folder / "raw" / "test_frames.csv").read_text().splitlines()[1:]]
    assert max(ts) > stop_lsl - 0.05


def test_stream_that_cannot_open_is_skipped(tmp_path, monkeypatch):
    from norad import recorder as R

    good = make_outlet("norad_test_good", ["a"], 10)
    bad = make_outlet("norad_test_bad", ["a"], 10)
    real = R._StreamWriter

    def writer(info, path):
        if info.name() == "norad_test_bad":
            raise TimeoutError("the operation failed due to a timeout.")
        return real(info, path)

    monkeypatch.setattr(R, "_StreamWriter", writer)
    rec = Recorder(tmp_path)
    folder = rec.start("p", "t")
    rec.stop()
    meta = json.loads((folder / "session.json").read_text())
    assert "norad_test_good" in meta["samples"]
    assert "norad_test_bad" in meta["skipped_streams"]
    del good, bad
