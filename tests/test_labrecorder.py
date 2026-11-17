import socket
import threading
from pathlib import Path

from norad import labrecorder
from norad.labrecorder import LabRecorder


def _fake_server():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    got = []

    def serve():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            with conn:
                while data := conn.recv(4096):
                    got.append(data.decode())

    threading.Thread(target=serve, daemon=True).start()
    return srv, got


def test_start_sends_commands(monkeypatch):
    monkeypatch.setattr(labrecorder, "UPDATE_WAIT_S", 0)
    srv, got = _fake_server()
    lr = LabRecorder(port=srv.getsockname()[1])
    assert lr.available()
    assert lr.start(Path("/r/x"))
    import time; time.sleep(0.3)
    text = "".join(got)
    order = [text.index(c) for c in ("update", "select all", "filename {root:/r/x} {template:recording.xdf}", "start")]
    assert order == sorted(order)
    srv.close()


def test_unavailable():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    lr = LabRecorder(port=port)
    assert lr.available() is False
    assert lr.start(Path("/r/x")) is False
    assert lr.stop() is False
