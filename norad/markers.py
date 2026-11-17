"""Operator markers (keys, clicker, notes) as an LSL string stream."""
import pylsl

from .lsl_io import make_outlet


class MarkerOutlet:
    def __init__(self):
        self._out = make_outlet("norad_markers", ["label", "text"], 0, fmt="string", stype="Markers")

    def push(self, label: str, text: str = "") -> float:
        t = pylsl.local_clock()
        self._out.push_sample([str(label), str(text)], t)
        return t
