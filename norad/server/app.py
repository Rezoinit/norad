"""norad web app: Connect, Run and live view. Start with `norad`."""
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, Response, send_from_directory
from flask_socketio import SocketIO

from ..config import REPO_ROOT, Config, load_config, save_config
from ..labrecorder import LabRecorder, launch as launch_labrecorder
from ..live import LiveHub
from ..markers import MarkerOutlet
from ..recorder import Recorder
from ..sources.nasal import NasalSource
from ..sources.polar import PolarSource, scan_polar
from ..sources.tobii import SceneCamera, TobiiSource
from ..tasks import ODDBALL, PSYCHOPY_APP, TaskRunner, psychopy_command

STATIC = Path(__file__).parent / "static"


def create_app(cfg: Config) -> tuple[Flask, SocketIO]:
    app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
    sio = SocketIO(app, async_mode="threading")
    sources: dict = {}
    scene = SceneCamera(cfg.tobii_ip)
    markers = MarkerOutlet()
    recorder = Recorder(cfg.results_dir)
    labrec = LabRecorder()
    rec_started = [0.0]
    control = threading.Lock()  # Start and Stop never overlap

    def start_source(key: str, src) -> None:
        old = sources.get(key)
        if old:
            old.stop()
        sources[key] = src
        src.start()

    @app.route("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.route("/participant")
    def participant():
        return send_from_directory(STATIC, "participant.html")

    @app.route("/scene.jpg")
    def scene_frame():
        """Newest scene-camera frame; the page asks for one about 10 times a second."""
        jpeg = scene.latest_jpeg
        if jpeg is None:
            return Response(status=204)
        return Response(jpeg, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

    @sio.on("connect_devices")
    def connect_devices(_=None):
        if not (sources.get("tobii") and sources["tobii"].running):
            start_source("tobii", TobiiSource(cfg.tobii_ip))
            scene.start()
        if not (sources.get("nasal") and sources["nasal"].running):
            start_source("nasal", NasalSource(cfg.nasal_port))
        if cfg.polar_address and not (sources.get("polar") and sources["polar"].running):
            start_source("polar", PolarSource(cfg.polar_address))

    @sio.on("tobii_calibrate")
    def tobii_calibrate(msg):
        src = sources.get("tobii")
        try:
            ok, text = src.calibrate(msg.get("participant", "")) if src else (False, "Tobii not connected.")
        except Exception as e:  # e.g. glasses dropped off WiFi mid-calibration
            ok, text = False, f"Calibration error: {e}"
        sio.emit("tobii_calibration", {"ok": ok, "message": text})

    @sio.on("marker")
    def marker(msg):
        markers.push(msg.get("label") or msg.get("key", "mark"), msg.get("text", ""))

    def begin_recording(participant: str, task: str) -> None:
        with control:
            if recorder.active:
                return
            try:
                folder = recorder.start(participant, task)
            except Exception as e:
                sio.emit("app_error", f"Could not start recording: {e}")
                return
            rec_started[0] = time.monotonic()
            if recorder.skipped:
                sio.emit("app_error", "Not recorded (could not open): " + ", ".join(recorder.skipped))
            xdf = labrec.start(folder)
            recorder.note(xdf=xdf)
            if not xdf:
                sio.emit("app_error", "XDF not recorded (LabRecorder not running); CSVs are saved.")

    def end_recording() -> None:
        with control:
            if recorder.active:
                labrec.stop()
                sio.emit("saved", str(recorder.stop()))

    task_who = ["", ""]  # participant, task name for the running task
    runner = TaskRunner(begin=lambda: begin_recording(*task_who), end=end_recording,
                        on_error=lambda m: sio.emit("app_error", m))

    @sio.on("start")
    def start(msg):
        begin_recording(msg.get("participant", ""), msg.get("task", ""))

    @sio.on("stop")
    def stop(_=None):
        runner.cancel()  # a running task ends too
        end_recording()

    @sio.on("oddball")
    def oddball(msg):
        if recorder.active or runner.running:
            sio.emit("app_error", "Stop the current recording first.")
            return
        if not PSYCHOPY_APP.exists():
            sio.emit("app_error", "PsychoPy is not installed (expected in /Applications).")
            return
        task_who[:] = [msg.get("participant", ""), "oddball"]
        runner.start(*psychopy_command(ODDBALL, "--wait-ready"))
        sio.emit("app_error", "Oddball starting on the participant screen. Recording begins automatically.")

    @sio.on("polar_scan")
    def polar_scan(_=None):
        try:
            sio.emit("polar_devices", scan_polar())
        except Exception as e:
            sio.emit("polar_devices", [])
            sio.emit("app_error", f"Bluetooth scan failed: {e}")

    @sio.on("polar_connect")
    def polar_connect(msg):
        cfg.polar_address = msg["address"]
        save_config(cfg)
        start_source("polar", PolarSource(cfg.polar_address))

    def status_loop():
        while True:
            try:
                send_status()
            except Exception as e:  # never let the status thread die: the UI depends on it
                print(f"[status] {e}")
            time.sleep(1.0)

    def send_status():
        devices = {k: {"connected": False, "rate_hz": 0, "error": None} for k in ("tobii", "nasal", "polar")}
        devices.update({k: s.status() for k, s in list(sources.items())})
        sio.emit("status", {
            "devices": devices,
            "polar_address": cfg.polar_address,
            "labrecorder": {"available": labrec.available()},
            "task_running": runner.running,
            "recording": {"active": recorder.active,
                          "folder": recorder.folder.name if recorder.folder else None,
                          "elapsed_s": round(time.monotonic() - rec_started[0]) if recorder.active else 0,
                          "streams": recorder.streams if recorder.active else []},
        })

    threading.Thread(target=status_loop, daemon=True).start()
    LiveHub(sio).start()
    return app, sio


def _port_in_use(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _log_to_file(path: Path) -> None:
    """Copy everything printed (Python and device libraries) to a log file, still showing it in Terminal."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tee = subprocess.Popen(["tee", str(path)], stdin=subprocess.PIPE)
    sys.stdout.flush()
    sys.stderr.flush()
    os.dup2(tee.stdin.fileno(), 1)
    os.dup2(tee.stdin.fileno(), 2)
    sys.stdout.reconfigure(line_buffering=True)


def main() -> None:
    cfg = load_config()
    url = f"http://127.0.0.1:{cfg.port}/"
    if _port_in_use(cfg.port):  # already running: just show it
        webbrowser.open(url)
        return
    _log_to_file(REPO_ROOT / "logs" / "norad.log")
    print(f"norad {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    launch_labrecorder()
    app, sio = create_app(cfg)
    threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    sio.run(app, host="127.0.0.1", port=cfg.port, allow_unsafe_werkzeug=True)
