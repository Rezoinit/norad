"""Live view feed: reads every LSL stream and sends small batches to the browser.

Display only. Saved data comes from the recorder; analysis runs offline.
"""
import threading
import time
from collections import deque

import numpy as np
import pylsl

from .lsl_io import find_streams

NASAL = "norad_nasal"
TOBII = "norad_tobii"
POLAR_HR = "norad_polar_hr"
HRV_WIN_S = 60.0
ENV_HZ = 20.0
MV_PER_COUNT = 2400 / 4096  # nasal ADC: 12 bit, 2.4 V reference (firmware AR_INTERNAL2V4)


def rms_envelope(x: np.ndarray, fs: float, win_s: float = 0.1) -> np.ndarray:
    """Causal moving RMS of x around its mean: the sound amplitude of a mic signal."""
    x = np.asarray(x, dtype=float)
    w = max(1, int(round(win_s * fs)))
    return np.sqrt(np.convolve((x - x.mean()) ** 2, np.ones(w) / w)[: len(x)])


def clean_beats(rr: np.ndarray) -> np.ndarray:
    """True for RR (ms) within 300-2000 ms and within 20% of the median of the 5 beats around it."""
    rr = np.asarray(rr, dtype=float)
    med = np.array([np.median(rr[max(0, i - 2):i + 3]) for i in range(len(rr))])
    return (rr >= 300) & (rr <= 2000) & (np.abs(rr - med) <= 0.2 * med)


def rmssd(rr: np.ndarray) -> float:
    """RMSSD (ms) from successive pairs of clean beats; NaN if under 80% of beats are clean."""
    rr = np.asarray(rr, dtype=float)
    ok = clean_beats(rr)
    pairs = ok[1:] & ok[:-1]
    if len(rr) < 3 or ok.mean() < 0.8:
        return float("nan")
    return float(np.sqrt(np.mean(np.diff(rr)[pairs] ** 2)))


def gaze_direction(gd_l, gd_r) -> list[float] | None:
    """Unit gaze direction: mean of the eyes that are tracked, or None if neither is."""
    eyes = [np.asarray(g, float) for g in (gd_l, gd_r) if g is not None and np.all(np.isfinite(g))]
    if not eyes:
        return None
    v = np.mean(eyes, axis=0)
    return (v / np.linalg.norm(v)).tolist()


class FixationDetector:
    """Live I-VT fixation detection (Salvucci & Goldberg 2000): angular gaze velocity below
    30 deg/s is fixation; runs shorter than 60 ms are not counted (Tobii I-VT defaults).
    Head-mounted gaze is relative to the head. Live estimate only."""

    def __init__(self, threshold_deg_s: float = 30.0, min_dur_s: float = 0.06):
        self.threshold, self.min_dur = threshold_deg_s, min_dur_s
        self._prev: tuple[float, np.ndarray] | None = None
        self._start: float | None = None  # start time of the current below-threshold run
        self._ends: deque[float] = deque()  # end times of completed fixations

    def update(self, t: float, direction) -> tuple[float, bool, float, int]:
        """Returns (velocity deg/s, in fixation, current fixation duration s, fixations in last 60 s)."""
        vel = float("nan")
        prev_t = self._prev[0] if self._prev is not None else None
        if direction is None:
            self._end(prev_t)
            self._prev = None
        else:
            d = np.asarray(direction, float)
            if self._prev is not None and t > prev_t:
                cos = np.clip(np.dot(d, self._prev[1]), -1.0, 1.0)
                vel = float(np.degrees(np.arccos(cos)) / (t - prev_t))
            self._prev = (t, d)
            if np.isfinite(vel) and vel >= self.threshold:
                self._end(prev_t)
            elif self._start is None:
                self._start = t
        while self._ends and self._ends[0] < t - 60.0:
            self._ends.popleft()
        dur = t - self._start if self._start is not None else 0.0
        in_fix = dur >= self.min_dur
        return vel, in_fix, dur if in_fix else 0.0, len(self._ends)

    def _end(self, last_t: float | None) -> None:
        """Close the current run at its last slow sample; count it if long enough."""
        if self._start is not None and last_t is not None and last_t - self._start >= self.min_dur:
            self._ends.append(last_t)
        self._start = None


class LiveHub:
    def __init__(self, sio):
        self.sio = sio
        self.inlets: dict[str, pylsl.StreamInlet] = {}
        self._nasal = deque(maxlen=2000)  # (t, mic1, mic2): last ~2 s at the sensor's ~840 Hz
        self._fix = FixationDetector()
        self._rr = deque()  # (t, rr_ms): beats of the last HRV_WIN_S seconds

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="livehub").start()

    def _resolve(self) -> None:
        for info in find_streams(wait=1.0):
            if info.name() not in self.inlets:
                self.inlets[info.name()] = pylsl.StreamInlet(
                    info, max_buflen=10, processing_flags=pylsl.proc_clocksync)

    def _loop(self) -> None:
        last_resolve = 0.0
        while True:
            if time.monotonic() - last_resolve > 5.0:
                self._resolve()
                last_resolve = time.monotonic()
            self._tick()
            time.sleep(0.1)

    def _tick(self) -> None:
        for name, inlet in list(self.inlets.items()):
            try:
                v, t = inlet.pull_chunk(timeout=0.0, max_samples=4000)
            except pylsl.LostError:
                continue
            if t and name == NASAL:
                name, (v, t) = "norad_nasal_env", self._nasal_envelope(v, t)
            if t and name == POLAR_HR and (hrv := self._hrv(v, t))[1]:
                self._emit("norad_hrv", *hrv)
            if t and name == TOBII:
                self._emit("norad_fixation", *self._fixations(v, t))
            if t:
                self._emit(name, v, t)

    def _emit(self, name: str, v, t) -> None:
        # JSON has no NaN (the browser drops the connection on it): send null instead
        v = [[None if isinstance(x, float) and x != x else x for x in row] for row in v]
        self.sio.emit("data", {"stream": name, "now": pylsl.local_clock(), "t": t, "v": v})

    def _fixations(self, v, t):
        """Per gaze sample: [velocity deg/s, in fixation 0/1, fixation duration s, fixations/min]."""
        rows = []
        for ts, row in zip(t, v):
            vel, in_fix, dur, per_min = self._fix.update(ts, gaze_direction(row[5:8], row[8:11]))
            rows.append([vel, int(in_fix), round(dur, 3), per_min])
        return rows, list(t)

    def _hrv(self, v, t):
        """Per new beat: [RMSSD ms] over the last 60 s of RR, once 60 s of beats are in."""
        rows, ts = [], []
        for tb, row in zip(t, v):
            if not np.isfinite(row[1]):  # report without a beat
                continue
            self._rr.append((tb, row[1]))
            while self._rr[0][0] < tb - HRV_WIN_S:
                self._rr.popleft()
            if tb - self._rr[0][0] >= HRV_WIN_S - 5:
                rows.append([round(rmssd([r for _, r in self._rr]), 1)])
                ts.append(tb)
        return rows, ts

    def _nasal_envelope(self, v, t):
        """Raw mic samples are unreadable on screen; send their 100 ms RMS envelope (mV) at ~20 Hz."""
        self._nasal.extend((ts, row[2], row[3]) for ts, row in zip(t, v))  # mic1, mic2 columns
        a = np.array(self._nasal)
        if len(a) < 20 or a[-1, 0] <= a[0, 0]:
            return [], []
        fs = (len(a) - 1) / (a[-1, 0] - a[0, 0])
        env = np.column_stack([rms_envelope(a[:, 1], fs), rms_envelope(a[:, 2], fs)]) * MV_PER_COUNT
        idx = np.arange(len(a) - min(len(t), len(a)), len(a))[:: max(1, round(fs / ENV_HZ))]
        return env[idx].tolist(), a[idx, 0].tolist()
