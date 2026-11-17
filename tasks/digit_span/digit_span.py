"""Spoken digit span (PsychoPy). Runs in PsychoPy's own Python; Norad starts it.

Each trial: 2 s fixation; digits spoken one per second; 2 s hold; the participant types
the digits back and presses Enter; 4 s rest. Typed (not spoken) recall, so speaking
does not disturb the breathing signal. Classic pupil-load design (Kahneman & Beatty, 1966).

Default: 16 easy trials (3 digits), about 4 min.
Graded (--graded): 8 trials each of easy (3), medium (5) and hard (7) digits, mixed in
random order, about 8 min.

Digits are spoken by the Mac's built-in voice, generated on first run into voice/
(leading and trailing silence removed, so markers sit on the speech onset).
Fixation cross on constant mid-grey; 10 s fixation baseline first.

LSL marker stream "digitspan_markers": task_start, trial_start:<level>,
digit:<d>:<pos>/<n>:<level>, hold:<level>, recall_start:<level>,
answer:<typed>:<correct|incorrect>:<level>, rest, task_end (or task_aborted).
"""
import argparse
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tasks/taskkit.py

LEVELS = {"easy": 3, "medium": 5, "hard": 7}  # digits per trial
TRIALS_DEFAULT = 16  # easy only
TRIALS_PER_LEVEL = 8  # graded
FIX_S, DIGIT_SOA_S, HOLD_S, REST_S, BASELINE_S = 2.0, 1.0, 2.0, 4.0, 10.0
VOICE_DIR = Path(__file__).resolve().parent / "voice"
DIGIT_KEYS = {**{str(d): str(d) for d in range(10)}, **{f"num_{d}": str(d) for d in range(10)}}


def make_trials(graded: bool, seed: int | None = None) -> list[tuple[str, list[int]]]:
    """[(level, digits)]. Digits never repeat within a trial; graded levels are mixed at random."""
    rng = random.Random(seed)
    levels = [lvl for lvl in LEVELS for _ in range(TRIALS_PER_LEVEL)] if graded else ["easy"] * TRIALS_DEFAULT
    rng.shuffle(levels)
    return [(lvl, rng.sample(range(10), LEVELS[lvl])) for lvl in levels]


def score(typed: str, digits: list[int]) -> bool:
    return typed.replace(" ", "") == "".join(map(str, digits))


def trim_silence(x, fs: int, threshold: float = 0.05, margin_s: float = 0.005):
    """Cut leading and trailing silence (below threshold x peak), keeping a small margin."""
    import numpy as np

    loud = np.flatnonzero(np.abs(x) > threshold * np.abs(x).max())
    m = int(margin_s * fs)
    return x[max(loud[0] - m, 0): loud[-1] + m + 1]


def ensure_voice() -> dict[int, Path]:
    """Spoken digits 0-9 as WAV files, made once with the Mac's built-in voice."""
    import warnings

    import numpy as np
    from scipy.io import wavfile

    files = {d: VOICE_DIR / f"{d}.wav" for d in range(10)}
    if all(f.exists() for f in files.values()):
        return files
    VOICE_DIR.mkdir(exist_ok=True)
    voices = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    voice = ["-v", "Samantha"] if "Samantha" in voices else []
    for d, wav in files.items():
        aiff = wav.with_suffix(".aiff")
        subprocess.run(["say", *voice, "-o", str(aiff), str(d)], check=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@44100", str(aiff), str(wav)], check=True)
        aiff.unlink()
        with warnings.catch_warnings():  # macOS adds an extra (harmless) chunk to its WAV files
            warnings.simplefilter("ignore")
            fs, x = wavfile.read(wav)
        wavfile.write(wav, fs, trim_silence(x.astype(np.float32) / 32768, fs).astype(np.float32))
    return files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graded", action="store_true", help="easy/medium/hard trials mixed at random")
    ap.add_argument("--trials", type=int, help="limit the number of trials (for checks)")
    ap.add_argument("--test", action="store_true", help="check run: small window, silent, no instructions, auto answers")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--wait-ready", action="store_true", help="wait for a line on stdin (recording running) before starting")
    args = ap.parse_args()

    from taskkit import Session
    from psychopy import sound

    files = ensure_voice()
    s = Session("digitspan_markers", test=args.test)
    spoken = {d: sound.Sound(str(f), speaker=s.speaker["name"], volume=s.volume) for d, f in files.items()}
    trials = make_trials(args.graded, args.seed)[: args.trials]
    fast = 0.1 if args.test else 1.0  # check runs shorten the waits (not the digit timing)

    s.start("You will hear digits, one per second.\n\nRemember them in order. When the screen asks,\n"
            "type them and press Enter.\n\nKeep your eyes on the cross while listening.", args.wait_ready)
    aborted = s.wait_until(s.now() + (1.0 if args.test else BASELINE_S))
    for level, digits in trials:
        if aborted:
            break
        t = s.now()
        s.mark(f"trial_start:{level}", t)
        t += FIX_S * fast
        n = len(digits)
        for i, d in enumerate(digits):  # schedule all digits exactly one second apart
            spoken[d].play(when=t + i * DIGIT_SOA_S)
            s.mark(f"digit:{d}:{i + 1}/{n}:{level}", t + i * DIGIT_SOA_S)
        t_hold = t + n * DIGIT_SOA_S
        s.mark(f"hold:{level}", t_hold)
        if s.wait_until(t_hold + HOLD_S * fast, names=("escape",)):
            aborted = True
            break

        s.mark(f"recall_start:{level}")
        s.event.clearEvents()  # keys pressed while listening don't count
        typed, t_enter = "", None
        while t_enter is None:
            s.show("Type the digits, then press Enter\n\n" + " ".join(typed))
            if args.test:  # check runs answer correctly by themselves
                s.core.wait(0.3)
                typed, t_enter = "".join(map(str, digits)), s.core.getTime()
                break
            for key, t_key in s.keys():
                if key == "escape":
                    aborted = True
                elif key in DIGIT_KEYS:
                    typed += DIGIT_KEYS[key]
                elif key == "backspace":
                    typed = typed[:-1]
                elif key in ("return", "num_enter") and typed:
                    t_enter = t_key
            if aborted:
                break
            s.core.wait(0.01, hogCPUperiod=0)
        if aborted:
            break
        result = "correct" if score(typed, digits) else "incorrect"
        s.mark_key(f"answer:{typed}:{result}:{level}", t_enter)
        s.show()
        s.mark("rest")
        aborted = s.wait_until(s.now() + REST_S * fast, names=("escape",))
    s.finish(aborted)


if __name__ == "__main__":
    main()
