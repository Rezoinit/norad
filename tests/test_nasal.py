import json
import threading
import time

import pylsl

from conftest import existing, new_stream

from norad.sources import nasal
from norad.sources.nasal import NasalSource, parse_line


def _line(t, seq):
    return json.dumps({"t": t, "seq": seq, "m1": 2000, "m2": 2100, "temp": 31.5})


def test_parse_line():
    assert parse_line(_line(3005, 1)) == {"t": 3005, "seq": 1, "m1": 2000, "m2": 2100, "temp": 31.5}
    assert parse_line('{"status":"ready","t":3001}') is None
    assert parse_line("garbage") is None


def test_reset_detected():
    ready = threading.Event()

    def lines():
        ready.wait(10)  # start sending only once the test inlet is connected
        for k in range(100):
            yield _line(3000 + 5 * k, k)
        for k in range(10):  # board reset: seq and board time restart
            yield _line(3000 + 5 * k, k)

    before = existing("norad_nasal")
    src = NasalSource(port=None, lines=lines())
    src.start()
    info = new_stream("norad_nasal", before)
    inlet = pylsl.StreamInlet(info)
    inlet.open_stream(timeout=5)
    time.sleep(0.2)
    ready.set()
    got = []
    deadline = time.time() + 4
    while len(got) < 110 and time.time() < deadline:
        _, ts = inlet.pull_chunk(timeout=0.5)
        got += ts
    assert len(got) == 110
    assert min(b - a for a, b in zip(got, got[1:])) > -0.1


def test_no_port_no_crash(monkeypatch):
    monkeypatch.setattr(nasal, "find_port", lambda: None)
    src = NasalSource(port=None)
    src.start()
    time.sleep(0.5)
    st = src.status()
    assert st["connected"] is False
    assert "not found" in st["error"]
