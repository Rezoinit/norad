import time

import pylsl


def existing(name: str) -> set[str]:
    """IDs of streams with this name that exist now (e.g. from the running app)."""
    return {i.uid() for i in pylsl.resolve_byprop("name", name, minimum=0, timeout=1.5)}


def new_stream(name: str, before: set[str], timeout: float = 5.0) -> pylsl.StreamInfo:
    """The stream with this name that was not there before: the test's own."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for i in pylsl.resolve_byprop("name", name, minimum=len(before) + 1, timeout=1.0):
            if i.uid() not in before:
                return i
    raise LookupError(name)
