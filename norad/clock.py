"""Map device timestamps onto the LSL clock.

Network/USB delay only ever makes a sample arrive later, never earlier, so the
smallest (arrival - device_time) seen recently is the best estimate of the
clock offset. A 30 s sliding window keeps up with slow clock drift.
"""
from collections import deque


class ClockMap:
    def __init__(self, window_s: float = 30.0):
        self.window_s = window_s
        self._mins: deque[tuple[float, float]] = deque()  # (arrival, offset), offsets increasing

    def map(self, device_t: float, arrival: float) -> float:
        offset = arrival - device_t
        while self._mins and self._mins[-1][1] >= offset:
            self._mins.pop()
        self._mins.append((arrival, offset))
        while self._mins[0][0] < arrival - self.window_s:
            self._mins.popleft()
        return device_t + self._mins[0][1]

    def reset(self) -> None:
        self._mins.clear()
