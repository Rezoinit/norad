"""Writes every LSL stream to raw/<stream>.csv plus session.json, one folder per recording.

Independent of LabRecorder, so CSVs are saved even if the XDF is not.
"""
import csv
import json
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import pylsl

from .config import REPO_ROOT
from .lsl_io import channel_labels, find_streams

SCHEMA_VERSION = 1


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "none"


def folder_name(when: datetime, participant: str, task: str) -> str:
    return f"{when:%Y-%m-%d_%H%M}_{_slug(participant)}_{_slug(task)}"


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


class _StreamWriter(threading.Thread):
    def __init__(self, info: pylsl.StreamInfo, path: Path):
        super().__init__(daemon=True, name=f"rec-{info.name()}")
        self.inlet = pylsl.StreamInlet(info, max_buflen=360, processing_flags=pylsl.proc_clocksync)
        self.labels = channel_labels(self.inlet.info(timeout=2))
        self.inlet.open_stream(timeout=2)
        self.path, self.rows = path, 0
        self.stop_at: float | None = None  # LSL time; samples after it are not written

    def run(self) -> None:
        with open(self.path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t_lsl", *self.labels])
            last_flush = time.monotonic()
            while True:
                v, t = self.inlet.pull_chunk(timeout=0.2)
                stop_t = self.stop_at  # read after pulling, so post-stop samples in this chunk are dropped
                for ts, row in zip(t, v):
                    if stop_t is not None and ts > stop_t:
                        break
                    w.writerow([f"{ts:.6f}", *row])
                    self.rows += 1
                if time.monotonic() - last_flush >= 1.0:
                    f.flush()
                    last_flush = time.monotonic()
                # done once data has passed the stop time, or after a 1.5 s grace for late frames
                if stop_t is not None and ((t and t[-1] > stop_t) or pylsl.local_clock() > stop_t + 1.5):
                    break
        self.inlet.close_stream()


class Recorder:
    def __init__(self, results_dir: Path):
        self.results_dir = Path(results_dir)
        self.active = False
        self.streams: list[str] = []
        self.skipped: dict[str, str] = {}  # streams found but not openable at Start
        self.folder: Path | None = None
        self._writers: dict[str, _StreamWriter] = {}
        self._meta: dict = {}
        self._lock = threading.Lock()

    def start(self, participant: str, task: str, extra: dict | None = None) -> Path:
        with self._lock:
            if self.active:
                raise RuntimeError("Already recording")
            return self._start(participant, task, extra)

    def _start(self, participant: str, task: str, extra: dict | None) -> Path:
        now = datetime.now()
        base = self.results_dir / folder_name(now, participant, task)
        folder, n = base, 1
        while folder.exists():
            n += 1
            folder = base.with_name(f"{base.name}_{n}")
        (folder / "raw").mkdir(parents=True)
        infos = {}
        for info in find_streams(wait=2.0):  # long enough not to miss a device
            infos.setdefault(info.name(), info)
        self._writers, skipped = {}, {}
        for name, info in infos.items():
            fname = re.sub(r"[^A-Za-z0-9_-]+", "_", name.removeprefix("norad_"))
            try:
                self._writers[name] = _StreamWriter(info, folder / "raw" / f"{fname}.csv")
            except Exception as e:  # e.g. the device vanished just now: record the rest
                skipped[name] = str(e)
        for w in self._writers.values():
            w.start()
        self.folder, self.streams, self.active = folder, sorted(self._writers), True
        self.skipped = skipped
        self._meta = {
            "schema_version": SCHEMA_VERSION,
            "participant": participant,
            "task": task,
            "start_wall": now.isoformat(timespec="seconds"),
            "start_lsl": pylsl.local_clock(),
            "streams": {name: {"labels": w.labels, "srate": infos[name].nominal_srate(),
                               "type": infos[name].type(), "source_id": infos[name].source_id(),
                               "file": f"raw/{w.path.name}"}
                        for name, w in self._writers.items()},
            "skipped_streams": skipped,
            "software": _git_commit(),
            "extra": extra or {},
        }
        self._write_meta()
        return folder

    def stop(self) -> Path:
        if not self.active:
            return self.folder
        stop_lsl = pylsl.local_clock()
        for w in self._writers.values():
            w.stop_at = stop_lsl
        for w in self._writers.values():
            w.join(timeout=3)
        self._meta.update(stop_wall=datetime.now().isoformat(timespec="seconds"),
                          stop_lsl=stop_lsl,
                          samples={name: w.rows for name, w in self._writers.items()})
        self._write_meta()
        self.active = False
        return self.folder

    def note(self, **extra) -> None:
        """Add facts learned after start (e.g. whether the XDF is being written)."""
        self._meta["extra"].update(extra)
        self._write_meta()

    def _write_meta(self) -> None:
        (self.folder / "session.json").write_text(json.dumps(self._meta, indent=2))
