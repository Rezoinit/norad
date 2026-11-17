"""Base class for device adapters: runs a read loop in a thread and never raises."""
import threading
import time
from abc import ABC, abstractmethod
from collections import deque


class Source(ABC):
    name = "source"

    def __init__(self):
        self.connected = False
        self.error: str | None = None
        self.running = False
        self._thread: threading.Thread | None = None
        self._counts: deque[list] = deque()  # [whole second, samples], last few seconds
        self._lock = threading.Lock()

    @abstractmethod
    def _run(self) -> None:
        """Blocking read loop; return when self.running is False."""

    def start(self) -> None:
        if self.running:
            return
        self.running, self.error = True, None
        self._thread = threading.Thread(target=self._guarded, daemon=True, name=self.name)
        self._thread.start()

    def _guarded(self) -> None:
        try:
            self._run()
        except Exception as e:  # a device problem must never crash the app
            self.error = str(e) or type(e).__name__
        finally:
            self.connected = False
            self.running = False

    def stop(self) -> None:
        self.running = False

    def _count(self, n: int) -> None:
        sec = int(time.monotonic())
        with self._lock:
            if self._counts and self._counts[-1][0] == sec:
                self._counts[-1][1] += n
            else:
                self._counts.append([sec, n])
            while self._counts[0][0] < sec - 3:
                self._counts.popleft()

    def status(self) -> dict:
        sec = int(time.monotonic())
        with self._lock:  # rate over the last two complete seconds
            recent = sum(n for s, n in self._counts if sec - 2 <= s < sec)
        return {"connected": self.connected, "rate_hz": round(recent / 2.0, 1), "error": self.error}
