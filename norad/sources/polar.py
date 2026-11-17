"""Polar H10 chest strap over Bluetooth: ECG (130 Hz), chest acceleration (200 Hz), HR/RR.

Bluetooth runs in a child process (`python -m norad.sources.polar ...`):
macOS kills a process that uses Bluetooth without permission, and that must not
take the whole app down.
"""
import asyncio
import json
import subprocess
import sys
import time

import pylsl

from ..clock import ClockMap
from ..lsl_io import make_outlet
from .base import Source

ECG_FS, ACC_FS = 130.0, 200.0
NO_CONTACT = "Polar: poor skin contact. Wet the electrodes and tighten the strap."
BLOCKED = ("Bluetooth blocked by macOS. Start Norad from the Desktop icon and allow "
           "Bluetooth when asked (System Settings > Privacy & Security > Bluetooth).")


def frame_times(t_last: float, n: int, fs: float) -> list[float]:
    """Times of n samples at rate fs whose last sample is at t_last."""
    return [t_last - (n - 1 - i) / fs for i in range(n)]


def hr_rows(t_s: float, avg_hr: float, rr_ms: list) -> list[tuple[float, list[float]]]:
    """Rows [hr_bpm, rr_ms] from one heart-rate report (about once a second). Each beat
    interval gets its own row, timed back from the report; a report without one still
    gives the strap's heart rate."""
    if not rr_ms:
        return [(t_s, [float(avg_hr), float("nan")])]
    ends = [t_s - sum(rr_ms[i + 1:]) / 1000 for i in range(len(rr_ms))]
    return [(t, [float(avg_hr), float(rr)]) for t, rr in zip(ends, rr_ms)]


def _child(*args: str) -> list[str]:
    return [sys.executable, "-m", "norad.sources.polar", *args]


def scan_polar(timeout: float = 5.0) -> list[dict]:
    p = subprocess.run(_child("scan", str(timeout)), capture_output=True, text=True, timeout=timeout + 20)
    if p.returncode != 0:
        raise RuntimeError(BLOCKED if p.returncode < 0 else p.stderr.strip()[-300:])
    return json.loads(p.stdout)


class PolarSource(Source):
    name = "polar"

    def __init__(self, address: str, cmd: list[str] | None = None):
        super().__init__()
        self.address = address
        self.cmd = cmd or _child("stream", address)
        self._proc: subprocess.Popen | None = None

    def _run(self) -> None:
        # stderr is merged into stdout and always read, so the child can never block on a full pipe
        self._proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        other = ""
        for line in self._proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                other = line.strip() or other
                continue
            self.connected = msg.get("connected", self.connected)
            self.error = msg.get("error", self.error)
            self._count(msg.get("count", 0))
        code = self._proc.wait()
        if self.running and code != 0:
            self.error = self.error or (BLOCKED if code < 0 else other[-300:] or f"exit code {code}")

    def stop(self) -> None:
        super().stop()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


# ── child process ─────────────────────────────────────────────

def _say(**msg) -> None:
    print(json.dumps(msg), flush=True)


async def _scan(timeout: float) -> None:
    from bleak import BleakScanner

    devices = await BleakScanner.discover(timeout=timeout)
    print(json.dumps([{"name": d.name, "address": d.address}
                      for d in devices if (d.name or "").startswith("Polar H10")]))


async def _stream(address: str) -> None:
    from bleak import BleakClient
    from bleakheart import HeartRate, PolarMeasurementData

    clock = ClockMap()
    ecg_out = make_outlet("norad_polar_ecg", ["ecg_uv"], ECG_FS, source_id=f"polar_ecg_{address}")
    acc_out = make_outlet("norad_polar_acc", ["acc_x_mg", "acc_y_mg", "acc_z_mg"], ACC_FS,
                          source_id=f"polar_acc_{address}")
    hr_out = make_outlet("norad_polar_hr", ["hr_bpm", "rr_ms"], 0, source_id=f"polar_hr_{address}")
    n_ecg = 0

    def on_frame(frame):
        nonlocal n_ecg
        kind, t_ns, samples = frame
        t_last = clock.map(t_ns / 1e9, pylsl.local_clock())
        fs, out = (ECG_FS, ecg_out) if kind == "ECG" else (ACC_FS, acc_out)
        rows = [[s] if kind == "ECG" else list(s) for s in samples]
        for row, t in zip(rows, frame_times(t_last, len(rows), fs)):
            out.push_sample(row, t)
        if kind == "ECG":
            n_ecg += len(rows)

    def on_hr(report):
        _, t_ns, (avg_hr, rr_ms), _ = report
        t = pylsl.local_clock() - (time.time() - t_ns / 1e9)
        for ts, row in hr_rows(t, avg_hr, rr_ms):
            hr_out.push_sample(row, ts)

    async with BleakClient(address, timeout=20.0) as client:
        pmd = PolarMeasurementData(client, callback=on_frame)
        for meas in ("ECG", "ACC"):
            code, msg, _ = await pmd.start_streaming(meas)
            if code != 0:
                raise RuntimeError(f"H10 {meas}: {msg}")
        await HeartRate(client, callback=on_hr, unpack=False,
                        contact_callback=lambda: _say(error=None),
                        contact_lost_callback=lambda: _say(error=NO_CONTACT)).start_notify()
        _say(connected=True, error=None)
        while client.is_connected:
            await asyncio.sleep(1.0)
            _say(count=n_ecg)
            n_ecg = 0
    _say(connected=False, error="Bluetooth connection lost")


if __name__ == "__main__":
    try:
        if sys.argv[1] == "scan":
            asyncio.run(_scan(float(sys.argv[2])))
        else:
            asyncio.run(_stream(sys.argv[2]))
    except Exception as e:
        _say(connected=False, error=str(e) or type(e).__name__)
        sys.exit(1)
