"""Shared PsychoPy helpers for Norad tasks: participant screen, LSL markers, keys.

Runs in PsychoPy's own Python. PsychoPy is imported only when a Session starts, so
the task design functions can be tested without it.
"""
import sys


class Session:
    """Mid-grey participant screen with a fixation cross, and an LSL marker stream whose
    timestamps are on the shared LSL clock (sound onsets and key presses converted)."""

    def __init__(self, stream: str, test: bool = False):
        import psychtoolbox as ptb
        import pyglet
        import pylsl
        import sounddevice as sd
        from psychopy import core, event, visual

        self.ptb, self.core, self.event, self.test = ptb, core, event, test
        self.out = pylsl.StreamOutlet(pylsl.StreamInfo(stream, "Markers", 1, 0, pylsl.cf_string, f"norad_{stream}"))
        self.to_lsl = pylsl.local_clock() - ptb.GetSecs()  # steady clocks: one offset converts each
        self.key_to_lsl = pylsl.local_clock() - core.getTime()
        self.speaker = sd.query_devices(kind="output")
        self.volume = 0.0 if test else 1.0  # check runs are silent

        screens = pyglet.canvas.get_display().get_screens()  # last screen = participant monitor
        size = (800, 600) if test else (screens[-1].width, screens[-1].height)
        self.win = visual.Window(size=size, fullscr=not test, screen=len(screens) - 1,
                                 color=(0, 0, 0), units="height", allowGUI=test)  # (0,0,0) = mid-grey
        self.win.mouseVisible = False
        self.cross = visual.ShapeStim(self.win, vertices="cross", size=0.06, lineColor=None, fillColor=(-1, -1, -1))
        self.text = visual.TextStim(self.win, height=0.035, color=(-1, -1, -1), wrapWidth=1.2)

    def now(self) -> float:
        return self.ptb.GetSecs()

    def mark(self, label: str, t: float | None = None) -> None:
        """Marker at sound-clock time t (default: now)."""
        self.out.push_sample([label], (t if t is not None else self.now()) + self.to_lsl)

    def mark_key(self, label: str, t_key: float) -> None:
        self.out.push_sample([label], t_key + self.key_to_lsl)

    def show(self, msg: str | None = None) -> None:
        """Text on grey, or the fixation cross when msg is None."""
        if msg:
            self.text.setText(msg)
            self.text.draw()
        else:
            self.cross.draw()
        self.win.flip()

    def keys(self, names=None) -> list[tuple[str, float]]:
        """Key presses since last call, from the task window (no special macOS permission)."""
        return self.event.getKeys(names, timeStamped=True)

    def wait_until(self, t: float, on_key=None, names=("space", "escape")) -> bool:
        """Wait until sound-clock time t, checking keys every 5 ms. Returns True if Escape."""
        while self.now() < t:
            for key, t_key in self.keys(list(names)):
                if key == "escape":
                    return True
                if on_key:
                    on_key(key, t_key)
            self.core.wait(0.005, hogCPUperiod=0)
        return False

    def start(self, instructions: str, wait_ready: bool) -> None:
        if wait_ready:  # Norad says when the recording is running, so no marker is missed
            self.show("Preparing…")
            sys.stdin.readline()
        if not self.test:
            self.show(instructions + "\n\nPress SPACE to start.")
            self.event.waitKeys(keyList=["space"])
        latency_ms = self.speaker["default_low_output_latency"] * 1000
        self.mark(f"info: audio={self.speaker['name']} latency_ms={latency_ms:.0f}")
        self.show()
        self.mark("task_start")

    def finish(self, aborted: bool) -> None:
        if aborted:
            self.mark("task_aborted")
        else:
            self.core.wait(2.0)
            self.mark("task_end")
            self.show("Done. Thank you.")
            self.core.wait(2.0)
        self.win.close()
        self.core.quit()
