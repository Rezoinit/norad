"""Run a PsychoPy task and record for exactly as long as it runs."""
import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pylsl

from .config import REPO_ROOT

PSYCHOPY_APP = Path("/Applications/PsychoPy.app")
ODDBALL = REPO_ROOT / "tasks" / "oddball" / "oddball.py"
DIGIT_SPAN = REPO_ROOT / "tasks" / "digit_span" / "digit_span.py"


@dataclass(frozen=True)
class Task:
    label: str  # recording folder name
    script: Path
    args: tuple[str, ...]
    stream: str  # the task's LSL marker stream


TASKS = {
    "oddball": Task("oddball", ODDBALL, (), "oddball_markers"),
    "oddball_graded": Task("oddball-graded", ODDBALL, ("--graded",), "oddball_markers"),
    "digit_span": Task("digit-span", DIGIT_SPAN, (), "digitspan_markers"),
    "digit_span_graded": Task("digit-span-graded", DIGIT_SPAN, ("--graded",), "digitspan_markers"),
}


def psychopy_command(script, *args: str) -> tuple[list[str], dict]:
    """Command and environment to run a script with PsychoPy's own Python."""
    env = {**os.environ, "PYTHONHOME": str(PSYCHOPY_APP / "Contents" / "Resources")}
    return [str(PSYCHOPY_APP / "Contents" / "MacOS" / "python"), str(script), *args], env


class TaskRunner:
    """Starts the task; once its marker stream exists, calls begin() (start recording);
    when the task ends or is cancelled, calls end() (stop recording)."""

    def __init__(self, begin: Callable[[], object], end: Callable[[], object],
                 on_error: Callable[[str], object] = print):
        self.begin, self.end, self.on_error = begin, end, on_error
        self._proc: subprocess.Popen | None = None
        self.running = False

    def start(self, cmd: list[str], env: dict | None = None, stream: str = "oddball_markers",
              wait_s: float = 60.0) -> None:
        if self.running:
            return
        self.running = True
        self._proc = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE, text=True)  # output -> app log
        threading.Thread(target=self._watch, args=(stream, wait_s), daemon=True, name="task").start()

    def _watch(self, stream: str, wait_s: float) -> None:
        proc, recording = self._proc, False
        try:
            for _ in range(int(wait_s)):  # the task creates its marker stream when it starts
                if proc.poll() is not None:
                    self.on_error(f"Task ended before it started (exit code {proc.returncode}). See logs/norad.log.")
                    return
                if pylsl.resolve_byprop("name", stream, timeout=1.0):
                    break
            else:
                self.on_error("Task did not start in time.")
                proc.terminate()
                return
            self.begin()
            recording = True
            try:  # tell the task the recording is running (tasks started with --wait-ready)
                proc.stdin.write("ready\n")
                proc.stdin.flush()
            except OSError:
                pass
            proc.wait()
        except Exception as e:
            self.on_error(f"Task error: {e}")
        finally:
            if recording:
                self.end()
            self.running = False

    def cancel(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
