"""Tobii Pro Glasses 2 over WiFi: gaze + pupil (~50 Hz), head IMU (~100 Hz), scene camera.

Every data packet the glasses send is read, not the library's "latest valid value"
snapshot (which repeats the last pupil during blinks and drops invalid frames).
Packets of one eye-tracking frame share a gaze index (`gidx`); each frame becomes one
row, with NaN for any eye or gaze value the glasses marked invalid.
"""
import json
import os
import queue
import threading
import time

import pylsl

from ..clock import ClockMap
from ..config import REPO_ROOT
from ..lsl_io import make_outlet
from .base import Source

GAZE_CHANNELS = ["tobii_ts_us", "gaze_x", "gaze_y", "pupil_l_mm", "pupil_r_mm",
                 "gd_l_x", "gd_l_y", "gd_l_z", "gd_r_x", "gd_r_y", "gd_r_z"]
IMU_CHANNELS = ["tobii_ts_us", "acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z"]
NAN = float("nan")
NO_DATA_S = 3.0  # no packet for this long = glasses gone (e.g. WiFi dropped)
PACKET_LOG = REPO_ROOT / "logs" / "tobii_packets.jsonl"
PACKET_LOG_N = 2000
SCENE_WIDTH = 640  # pixels, for the live panel


def _valid(p: dict, key: str):
    return p.get(key) if p.get("s", 1) == 0 else None


class FrameBuilder:
    """Turns the glasses' packet stream into one gaze row per frame and one IMU row per accelerometer packet."""

    def __init__(self):
        self._key = None
        self._frame: dict = {}
        self._gyro = [NAN] * 3

    def add(self, p: dict) -> tuple[list, list]:
        """Returns (gaze rows, imu rows) completed by this packet: [(ts_us, values), ...]."""
        if "ac" in p or "gy" in p:
            return [], self._imu(p)
        if not any(k in p for k in ("pc", "pd", "gd", "gp", "gp3")):
            return [], []  # video timestamps etc.
        key = p.get("gidx", p.get("ts"))
        done = []
        if self._key is not None and key != self._key:
            done = self._flush()
        self._key = key
        f = self._frame
        f.setdefault("ts", p.get("ts"))
        if "eye" in p:
            for k in ("pd", "gd"):
                if k in p:
                    f[(p["eye"], k)] = _valid(p, k)
        elif "gp" in p:
            f["ts"], f["gp"] = p.get("ts", f["ts"]), _valid(p, "gp")
        return done, []

    def _flush(self) -> list:
        f, self._frame = self._frame, {}
        gp = f.get("gp") or [NAN, NAN]
        pupils = [f.get((e, "pd")) for e in ("left", "right")]
        pupils = [float(x) if x is not None and x > 0 else NAN for x in pupils]
        dirs = [f.get((e, "gd")) or [NAN] * 3 for e in ("left", "right")]
        return [(f["ts"], [float(gp[0]), float(gp[1]), *pupils, *map(float, dirs[0] + dirs[1])])]

    def _imu(self, p: dict) -> list:
        if "gy" in p:
            self._gyro = [float(x) for x in (_valid(p, "gy") or [NAN] * 3)]
            return []
        ac = _valid(p, "ac") or [NAN] * 3
        return [(p["ts"], [float(x) for x in ac] + self._gyro)]


def _capturing_controller(on_packet):
    """The library's controller, also handing every received packet to on_packet."""
    from tobiiglassesctrl import TobiiGlassesController

    class Capturing(TobiiGlassesController):
        def __refresh_data__(self, jsondata):  # called by the library for each packet
            on_packet(jsondata)
            super().__refresh_data__(jsondata)

    return Capturing


class TobiiSource(Source):
    name = "tobii"

    def __init__(self, ip: str):
        super().__init__()
        self.ip = ip
        self.clock = ClockMap()
        self._packets: queue.Queue = queue.Queue()
        self.ctrl = None  # the glasses' controller while connected

    def calibrate(self, participant: str) -> tuple[bool, str]:
        """Tobii one-point calibration: the participant looks at the centre of the card."""
        ctrl = self.ctrl
        if ctrl is None:
            return False, "Tobii not connected."
        project = ctrl.create_project("norad")
        person = ctrl.create_participant(project, participant or "pilot")
        calibration = ctrl.create_calibration(project, person)
        ctrl.start_calibration(calibration)
        if ctrl.wait_until_calibration_is_done(calibration):
            return True, "Tobii calibrated."
        return False, "Calibration failed: hold the card about 1 m away, look at its centre, try again."

    def _run(self) -> None:
        # video_scene=True keeps the glasses' live video on (needed by SceneCamera's RTSP stream)
        tobii = _capturing_controller(self._packets.put)(self.ip, video_scene=True, timeout=5)
        tobii.start_streaming()
        self.ctrl = tobii
        # Rate 0 = irregular: frames can be lost over WiFi, so XDF readers must not
        # re-space timestamps as if every 50 Hz frame were present.
        try:
            self._gaze = make_outlet("norad_tobii", GAZE_CHANNELS, 0, fmt="double64", source_id=f"tobii_{self.ip}")
            self._imu = make_outlet("norad_tobii_imu", IMU_CHANNELS, 0, fmt="double64", source_id=f"tobii_imu_{self.ip}")
            fb = FrameBuilder()
            PACKET_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(PACKET_LOG, "w") as log:  # first packets, raw, for checking timing
                n_logged = 0
                while self.running:
                    if not tobii.streaming:
                        raise RuntimeError("Tobii not reachable. Is the Mac on the Tobii WiFi?")
                    try:
                        p = self._packets.get(timeout=NO_DATA_S)
                    except queue.Empty:
                        raise RuntimeError("Tobii data stopped. Is the Mac still on the Tobii WiFi?") from None
                    now = pylsl.local_clock()
                    if n_logged < PACKET_LOG_N:
                        log.write(json.dumps({"t_arrival": now, **p}) + "\n")
                        n_logged += 1
                    gaze, imu = fb.add(p)
                    for ts, v in gaze:
                        self._gaze.push_sample([ts, *v], self.clock.map(ts / 1e6, now))
                        self.connected = True
                        self._count(1)
                    for ts, v in imu:
                        self._imu.push_sample([ts, *v], self.clock.map(ts / 1e6, now))
        finally:
            self.ctrl = None
            tobii.stop_streaming()


class SceneCamera:
    """Latest scene-camera frame as JPEG, read over RTSP in a background thread."""

    def __init__(self, ip: str):
        self.ip = ip
        self.latest_jpeg: bytes | None = None
        self.running = False

    def start(self) -> None:
        if not self.running:
            self.running = True
            threading.Thread(target=self._run, daemon=True, name="scene").start()

    def _run(self) -> None:
        import cv2

        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        # without a read timeout a stalled stream blocks forever and is never retried
        params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000]
        while self.running:
            cap = cv2.VideoCapture(f"rtsp://{self.ip}:8554/live/scene", cv2.CAP_FFMPEG, params)
            if cap.isOpened():
                print(f"[scene] {time.strftime('%H:%M:%S')} camera stream opened", flush=True)
            frames, t_report = 0, time.monotonic()
            while self.running and cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break
                small = cv2.resize(frame, (SCENE_WIDTH, SCENE_WIDTH * frame.shape[0] // frame.shape[1]),
                                   interpolation=cv2.INTER_AREA)  # the panel is small; send less
                self.latest_jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
                frames += 1
                if time.monotonic() - t_report >= 10:
                    print(f"[scene] {time.strftime('%H:%M:%S')} {frames} frames in 10 s", flush=True)
                    frames, t_report = 0, time.monotonic()
            if self.latest_jpeg is not None:
                print(f"[scene] {time.strftime('%H:%M:%S')} camera stream lost, retrying", flush=True)
            cap.release()
            self.latest_jpeg = None
            time.sleep(1.0)
