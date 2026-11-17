import csv
import sys
import time

from norad.recorder import Recorder
from norad.tasks import TaskRunner, psychopy_command

FAKE_TASK = """
import time, pylsl
out = pylsl.StreamOutlet(pylsl.StreamInfo("test_task_markers", "Markers", 1, 0, pylsl.cf_string, "fake"))
time.sleep(8)  # the recorder needs a few seconds to find and connect to streams
for m in ("task_start", "standard", "task_end"):
    out.push_sample([m]); time.sleep(0.2)
time.sleep({linger})
"""


def _runner(tmp_path):
    rec = Recorder(tmp_path)
    log = []
    runner = TaskRunner(begin=lambda: log.append(rec.start("p", "fake")),
                        end=lambda: log.append(rec.stop()))
    return runner, rec, log


def test_records_while_task_runs(tmp_path):
    runner, rec, log = _runner(tmp_path)
    runner.start([sys.executable, "-c", FAKE_TASK.format(linger=0.5)], stream="test_task_markers")
    deadline = time.time() + 40
    while (runner.running or rec.active) and time.time() < deadline:
        time.sleep(0.2)
    assert not runner.running and not rec.active and len(log) == 2
    rows = list(csv.reader(open(log[0] / "raw" / "test_task_markers.csv")))
    assert [r[1] for r in rows[1:]] == ["task_start", "standard", "task_end"]


def test_cancel_stops_task_and_recording(tmp_path):
    runner, rec, log = _runner(tmp_path)
    runner.start([sys.executable, "-c", FAKE_TASK.format(linger=60)], stream="test_task_markers")
    deadline = time.time() + 30
    while not rec.active and time.time() < deadline:
        time.sleep(0.2)
    runner.cancel()
    deadline = time.time() + 10
    while (runner.running or rec.active) and time.time() < deadline:
        time.sleep(0.2)
    assert not runner.running and not rec.active


def test_psychopy_command_uses_its_python():
    cmd, env = psychopy_command("task.py", "--seed", "1")
    assert cmd[0].endswith("PsychoPy.app/Contents/MacOS/python") and cmd[1:] == ["task.py", "--seed", "1"]
    assert env["PYTHONHOME"].endswith("PsychoPy.app/Contents/Resources")


def test_task_told_when_recording_runs(tmp_path):
    """The task waits for 'ready' on stdin, sent only after recording started."""
    rec = Recorder(tmp_path)
    started = []
    runner = TaskRunner(begin=lambda: started.append(rec.start("p", "fake")), end=rec.stop)
    code = ("import sys, time, pylsl\n"
            "out = pylsl.StreamOutlet(pylsl.StreamInfo('test_task_markers', 'Markers', 1, 0, pylsl.cf_string, 'fake'))\n"
            "sys.stdin.readline()\n"
            "out.push_sample(['task_start']); time.sleep(1)")
    runner.start([sys.executable, "-c", code], stream="test_task_markers")
    deadline = time.time() + 40
    while (runner.running or rec.active) and time.time() < deadline:
        time.sleep(0.2)
    rows = list(csv.reader(open(started[0] / "raw" / "test_task_markers.csv")))
    assert [r[1] for r in rows[1:]] == ["task_start"]  # first marker not lost
