import os
import subprocess
import sys
from pathlib import Path


def test_lsl_limited_to_this_computer():
    """WiFi changes (e.g. joining the Tobii network) must not break stream connections."""
    out = subprocess.run([sys.executable, "-c", "import norad, os; print(os.environ['LSLAPICFG'])"],
                         capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "LSLAPICFG"})
    cfg = Path(out.stdout.strip())
    assert cfg.is_file()
    assert "ResolveScope = machine" in cfg.read_text()


def test_labrecorder_gets_same_lsl_config(monkeypatch):
    from norad import labrecorder

    calls = []
    monkeypatch.setattr(labrecorder.shutil, "which", lambda _: None)
    monkeypatch.setattr(labrecorder.subprocess, "run", lambda cmd, **k: calls.append(cmd))
    labrecorder.launch()
    assert any(a.startswith("LSLAPICFG=") for a in calls[0])


def test_streams_from_separate_processes_are_found():
    """The Polar process and the PsychoPy task are separate programs; their streams must be found."""
    import time

    import pylsl

    import norad  # noqa: F401  (sets the LSL config, inherited by the children)

    code = ("import time, pylsl; o = pylsl.StreamOutlet(pylsl.StreamInfo('xproc_test_{k}', 'Markers', 1, 0, "
            "pylsl.cf_string, 'xproc{k}')); time.sleep(8)")
    kids = [subprocess.Popen([sys.executable, "-c", code.format(k=k)]) for k in range(2)]
    try:
        time.sleep(1.5)
        found = {i.name() for i in pylsl.resolve_streams(2.0)}
        assert {"xproc_test_0", "xproc_test_1"} <= found
    finally:
        for k in kids:
            k.terminate()
