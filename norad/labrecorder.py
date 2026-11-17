"""Drive LabRecorder (XDF writer) through its remote-control socket."""
import shutil
import socket
import subprocess
import time
from pathlib import Path

from . import LSL_CONFIG
from .config import REPO_ROOT

UPDATE_WAIT_S = 2.0  # LabRecorder needs a moment to refresh its stream list
CFG = REPO_ROOT / "scripts" / "labrecorder.cfg"


class LabRecorder:
    def __init__(self, host: str = "127.0.0.1", port: int = 22345):
        self.addr = (host, port)

    def available(self) -> bool:
        try:
            socket.create_connection(self.addr, timeout=0.5).close()
            return True
        except OSError:
            return False

    def _send(self, *commands: str, wait_after_first: float = 0.0) -> bool:
        try:
            with socket.create_connection(self.addr, timeout=2) as s:
                for i, cmd in enumerate(commands):
                    s.sendall(cmd.encode() + b"\n")
                    if i == 0 and wait_after_first:
                        time.sleep(wait_after_first)
            return True
        except OSError:
            return False

    def start(self, folder: Path) -> bool:
        return self._send("update", "select all",
                          f"filename {{root:{folder}}} {{template:recording.xdf}}", "start",
                          wait_after_first=UPDATE_WAIT_S)

    def stop(self) -> bool:
        return self._send("stop")


def launch() -> None:
    """Open LabRecorder with remote control enabled, if it is installed."""
    try:
        if shutil.which("LabRecorder"):
            subprocess.Popen(["LabRecorder", "-c", str(CFG)])  # inherits LSLAPICFG
        else:
            subprocess.run(["open", "-g", "--env", f"LSLAPICFG={LSL_CONFIG}", "-a", "LabRecorder",
                            "--args", "-c", str(CFG)], capture_output=True, timeout=10)
    except Exception:
        pass
