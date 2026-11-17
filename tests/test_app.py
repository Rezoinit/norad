import socket

from norad.config import Config
from norad.server import app as app_mod


def test_main_when_port_busy(monkeypatch):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()
    port = s.getsockname()[1]
    opened = []
    monkeypatch.setattr(app_mod, "load_config", lambda: Config(port=port))
    monkeypatch.setattr(app_mod.webbrowser, "open", opened.append)
    app_mod.main()
    assert opened == [f"http://127.0.0.1:{port}/"]
    s.close()


def test_log_file_captures_python_and_c_output(tmp_path):
    import subprocess
    import sys

    log = tmp_path / "logs" / "norad.log"
    code = (f"import os; from norad.server.app import _log_to_file; _log_to_file(__import__('pathlib').Path(r'{log}')); "
            "print('from python'); os.write(2, b'from C level\\n')")
    subprocess.run([sys.executable, "-c", code], timeout=30, capture_output=True)
    text = log.read_text()
    assert "from python" in text and "from C level" in text


def _test_app(monkeypatch, jpeg):
    class Scene:
        latest_jpeg = jpeg

        def __init__(self, ip):
            pass

        def start(self):
            pass

    class Quiet:
        def __init__(self, *a, **k):
            pass

        def start(self):
            pass

        def push(self, *a, **k):
            return 0.0

    monkeypatch.setattr(app_mod, "SceneCamera", Scene)
    monkeypatch.setattr(app_mod, "MarkerOutlet", Quiet)
    monkeypatch.setattr(app_mod, "LiveHub", Quiet)
    app, _ = app_mod.create_app(Config(port=0))
    return app.test_client()


def test_scene_frame_endpoint(monkeypatch):
    assert _test_app(monkeypatch, None).get("/scene.jpg").status_code == 204  # no camera yet
    r = _test_app(monkeypatch, b"\xff\xd8jpeg").get("/scene.jpg")
    assert r.status_code == 200 and r.mimetype == "image/jpeg" and r.data == b"\xff\xd8jpeg"
    assert "no-store" in r.headers["Cache-Control"]


def test_unknown_task_reports_error(monkeypatch):
    for name in ("SceneCamera", "MarkerOutlet", "LiveHub"):
        monkeypatch.setattr(app_mod, name, type(name, (), {"__init__": lambda self, *a, **k: None,
                                                           "start": lambda self: None, "latest_jpeg": None}))
    app, sio = app_mod.create_app(Config(port=0))
    client = sio.test_client(app)
    client.emit("task", {"name": "nope", "participant": "p"})
    errors = [m["args"][0] for m in client.get_received() if m["name"] == "app_error"]
    assert any("Unknown task" in e for e in errors)
