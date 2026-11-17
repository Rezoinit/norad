"""Auditory oddball (PsychoPy). Runs in PsychoPy's own Python; norad starts it.

Tones: standard 1000 Hz, deviant 1500 Hz, 100 ms with smooth on/off ramps, 80/20,
onset-to-onset interval jittered 1.5-2.5 s. The participant presses SPACE for the
high (deviant) tone. Fixation cross on constant mid-grey, so screen brightness never
moves the pupil. A 10 s fixation baseline comes before the first tone.

LSL marker stream "oddball_markers" (type Markers): task_start, standard, deviant,
response, task_end (or task_aborted), plus one audio-device info line. Tone markers
carry the scheduled sound onset; response markers the key-down time.
"""
import argparse
import random
import sys

STANDARD_HZ, DEVIANT_HZ, TONE_S = 1000, 1500, 0.1
SOA_S = (1.5, 2.5)
BASELINE_S = 10.0
LEAD_IN = 5  # first tones are always standard


def make_trials(n_standard: int = 120, n_deviant: int = 30, seed: int | None = None) -> list[tuple[str, float]]:
    """[(tone, seconds to the next tone onset)]. Deviants never come twice in a row."""
    rng = random.Random(seed)
    n = n_standard + n_deviant
    slots = n - LEAD_IN - (n_deviant - 1)  # choose k of these, then spread them apart by one
    picks = sorted(rng.sample(range(slots), n_deviant))
    deviants = {LEAD_IN + p + i for i, p in enumerate(picks)}
    return [("deviant" if i in deviants else "standard", rng.uniform(*SOA_S)) for i in range(n)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--standard", type=int, default=120)
    ap.add_argument("--deviant", type=int, default=30)
    ap.add_argument("--test", action="store_true", help="check run: small window, silent, no instructions, 1 s baseline")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--wait-ready", action="store_true", help="wait for a line on stdin (recording running) before starting")
    args = ap.parse_args()

    import psychtoolbox as ptb
    import pyglet
    import pylsl
    import sounddevice as sd
    from psychopy import core, event, sound, visual

    out = pylsl.StreamOutlet(pylsl.StreamInfo("oddball_markers", "Markers", 1, 0, pylsl.cf_string, "norad_oddball"))
    to_lsl = pylsl.local_clock() - ptb.GetSecs()  # steady clocks: one offset converts each
    key_to_lsl = pylsl.local_clock() - core.getTime()

    def mark(label: str, t_ptb: float | None = None) -> None:
        out.push_sample([label], (t_ptb if t_ptb is not None else ptb.GetSecs()) + to_lsl)

    speaker = sd.query_devices(kind="output")
    latency_ms = speaker["default_low_output_latency"] * 1000
    volume = 0.0 if args.test else 1.0
    tones = {"standard": sound.Sound(STANDARD_HZ, secs=TONE_S, hamming=True, speaker=speaker["name"], volume=volume),
             "deviant": sound.Sound(DEVIANT_HZ, secs=TONE_S, hamming=True, speaker=speaker["name"], volume=volume)}

    screens = pyglet.canvas.get_display().get_screens()  # last screen = participant monitor
    size = (800, 600) if args.test else (screens[-1].width, screens[-1].height)
    win = visual.Window(size=size, fullscr=not args.test, screen=len(screens) - 1,
                        color=(0, 0, 0), units="height", allowGUI=args.test)  # (0,0,0) = mid-grey
    win.mouseVisible = False
    cross = visual.ShapeStim(win, vertices="cross", size=0.06, lineColor=None, fillColor=(-1, -1, -1))
    text = visual.TextStim(win, height=0.035, color=(-1, -1, -1), wrapWidth=1.2)

    def show(msg: str | None) -> None:
        if msg:
            text.setText(msg)
            text.draw()
        else:
            cross.draw()
        win.flip()

    trials = make_trials(args.standard, args.deviant, args.seed)
    if args.wait_ready:  # norad says when the recording is running, so no marker is missed
        show("Preparing…")
        sys.stdin.readline()
    if not args.test:
        show("You will hear low and high tones.\n\nPress SPACE as fast as you can for the HIGH tone only.\n"
             "Keep your eyes on the cross.\n\nPress SPACE to start.")
        event.waitKeys(keyList=["space"])
    mark(f"info: audio={speaker['name']} latency_ms={latency_ms:.0f}")
    show(None)
    mark("task_start")
    t_next = ptb.GetSecs() + (1.0 if args.test else BASELINE_S)
    aborted = False
    for tone, soa in trials:
        tones[tone].play(when=t_next)
        mark(tone, t_next)
        t_end = t_next + soa
        while ptb.GetSecs() < t_end - 0.05:  # leave time to schedule the next tone
            # window key events (no special macOS permission); checked every 5 ms
            for key, t_key in event.getKeys(["space", "escape"], timeStamped=True):
                if key == "escape":
                    aborted = True
                    break
                out.push_sample(["response"], t_key + key_to_lsl)
            if aborted:
                break
            core.wait(0.005, hogCPUperiod=0)
        if aborted:
            break
        t_next = t_end
    if aborted:
        mark("task_aborted")
    else:
        core.wait(2.0)
        mark("task_end")
        show("Done. Thank you.")
        core.wait(2.0)
    win.close()
    core.quit()


if __name__ == "__main__":
    main()
