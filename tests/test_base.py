import threading
import time

from norad.sources.base import Source


class Dummy(Source):
    def _run(self):
        pass


def test_status_while_counting():
    src = Dummy()
    stop = False

    def hammer():
        while not stop:
            src._count(1)

    t = threading.Thread(target=hammer)
    t.start()
    try:
        end = time.monotonic() + 2.0
        while time.monotonic() < end:
            src.status()
    finally:
        stop = True
        t.join()
