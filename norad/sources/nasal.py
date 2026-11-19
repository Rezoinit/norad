"""Nasal breathing sensor (XIAO nRF52840, two mics) over USB serial, at full rate.

The board sends one JSON line per sample: {"t": board_ms, "seq", "m1", "m2", "temp"}.
"temp" is the chip temperature in 0.25 °C units; it is stored as °C.
Opening the port resets the board, which then waits ~3 s before sending.
"""
import json
import time
from typing import Iterable

import pylsl

from ..clock import ClockMap
from ..lsl_io import make_outlet
from .base import Source

CHANNELS = ["board_ms", "seq", "mic1", "mic2", "temp_c"]


def parse_line(line: str) -> dict | None:
    try:
        d = json.loads(line)
    except ValueError:
        return None
    if not isinstance(d, dict) or not {"t", "seq", "m1", "m2"} <= d.keys():
        return None
    return d


def find_port() -> str | None:
    from serial.tools import list_ports

    ports = list_ports.comports()
    for p in ports:
        if "usbmodem" in p.device.lower():
            return p.device
    for p in ports:
        if "USB" in (p.description or ""):
            return p.device
    return None


class NasalSource(Source):
    name = "nasal"

    def __init__(self, port: str | None = None, lines: Iterable[str] | None = None):
        super().__init__()
        self.port = port
        self._lines = lines
        self.clock = ClockMap()

    def _open_serial(self):
        import serial

        port = self.port or find_port()
        if not port:
            raise RuntimeError("Nasal sensor not found. Is the USB cable plugged in?")
        ser = serial.Serial(port, 115200, timeout=2)
        time.sleep(3.2)  # board resets on open and waits 3 s
        ser.reset_input_buffer()
        return ser

    def _serial_lines(self, ser) -> Iterable[str]:
        with ser:
            while self.running:
                yield ser.readline().decode("utf-8", errors="replace").strip()

    def _run(self) -> None:
        lines = self._lines if self._lines is not None else self._serial_lines(self._open_serial())
        # stream appears only once the device is open; kept on self so it outlives the loop
        out = self._out = make_outlet("norad_nasal", CHANNELS, 0, fmt="double64", source_id="norad_nasal")
        last_seq = None
        for line in lines:
            if not self.running:
                break
            d = parse_line(line)
            if d is None:
                continue
            if last_seq is not None and d["seq"] < last_seq:  # board was reset
                self.clock.reset()
            last_seq = d["seq"]
            t = self.clock.map(d["t"] / 1000.0, pylsl.local_clock())
            out.push_sample([d["t"], d["seq"], d["m1"], d["m2"], d.get("temp", float("nan")) / 4.0], t)
            self.connected = True
            self._count(1)
