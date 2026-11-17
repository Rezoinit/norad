"""Auditory oddball (PsychoPy). Runs in PsychoPy's own Python; Norad starts it.

Default: standard 1000 Hz, deviant 1500 Hz tones, 100 ms with smooth on/off ramps,
120/30 (80/20), onset-to-onset interval jittered 1.5-2.5 s; about 5 min.
Graded (--graded): three blocks, easy/medium/hard, in random order, each 80 standard +
20 deviant tones; only the deviant's pitch changes (LEVELS); 30 s fixation rest between
blocks; about 12 min.

The participant presses SPACE for the high (deviant) tone. Fixation cross on constant
mid-grey, so screen brightness never moves the pupil. 10 s fixation baseline first.

LSL marker stream "oddball_markers": task_start, standard, deviant, response, task_end
(or task_aborted), plus one audio-device info line. Graded runs add the level
(standard:easy, deviant:hard, …) and block_start:<level>, block_end:<level>, rest.
Tone markers carry the scheduled sound onset; response markers the key-down time.
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tasks/taskkit.py

STANDARD_HZ, DEVIANT_HZ, TONE_S = 1000, 1500, 0.1
LEVELS = {"easy": 1500, "medium": 1100, "hard": 1030}  # deviant pitch per level (Hz)
SOA_S = (1.5, 2.5)
BASELINE_S = 10.0
REST_S = 30.0  # between graded blocks
LEAD_IN = 5  # first tones of a block are always standard


def make_trials(n_standard: int = 120, n_deviant: int = 30, seed: int | None = None) -> list[tuple[str, float]]:
    """[(tone, seconds to the next tone onset)]. Deviants never come twice in a row."""
    rng = random.Random(seed)
    n = n_standard + n_deviant
    slots = n - LEAD_IN - (n_deviant - 1)  # choose k of these, then spread them apart by one
    picks = sorted(rng.sample(range(slots), n_deviant))
    deviants = {LEAD_IN + p + i for i, p in enumerate(picks)}
    return [("deviant" if i in deviants else "standard", rng.uniform(*SOA_S)) for i in range(n)]


def make_blocks(seed: int | None = None) -> list[str]:
    """Graded block order: each level once, shuffled."""
    order = list(LEVELS)
    random.Random(seed).shuffle(order)
    return order


def run_block(s, tones: dict, trials, t_start: float, suffix: str = "") -> tuple[float, bool]:
    """Play one block from t_start. Returns (time after the last tone's interval, aborted)."""
    t_next = t_start
    for tone, soa in trials:
        tones[tone].play(when=t_next)
        s.mark(tone + suffix, t_next)
        # stop 50 ms early to leave time to schedule the next tone
        if s.wait_until(t_next + soa - 0.05, on_key=lambda key, t: s.mark_key("response", t)):
            return t_next, True
        t_next += soa
    return t_next, False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graded", action="store_true", help="easy/medium/hard blocks in random order")
    ap.add_argument("--standard", type=int, help="standard tones (per block when graded)")
    ap.add_argument("--deviant", type=int, help="deviant tones (per block when graded)")
    ap.add_argument("--test", action="store_true", help="check run: small window, silent, no instructions, short waits")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--wait-ready", action="store_true", help="wait for a line on stdin (recording running) before starting")
    args = ap.parse_args()
    n_std = args.standard or (80 if args.graded else 120)
    n_dev = args.deviant or (20 if args.graded else 30)
    rng = random.Random(args.seed)

    from taskkit import Session
    from psychopy import sound

    s = Session("oddball_markers", test=args.test)

    def tone(hz):
        return sound.Sound(hz, secs=TONE_S, hamming=True, speaker=s.speaker["name"], volume=s.volume)

    standard = tone(STANDARD_HZ)
    if args.graded:
        blocks = [(level, {"standard": standard, "deviant": tone(LEVELS[level])}, ":" + level)
                  for level in make_blocks(rng.randrange(1 << 30))]
        intro = ("You will hear low tones and, now and then, a higher tone.\n\n"
                 "Press SPACE as fast as you can for the HIGHER tone only.\n"
                 "There are three parts with short breaks. In some parts the higher tone\n"
                 "is only slightly higher.\n\nKeep your eyes on the cross.")
    else:
        blocks = [(None, {"standard": standard, "deviant": tone(DEVIANT_HZ)}, "")]
        intro = ("You will hear low and high tones.\n\nPress SPACE as fast as you can for the HIGH tone only.\n"
                 "Keep your eyes on the cross.")

    s.start(intro, args.wait_ready)
    t = s.now() + (1.0 if args.test else BASELINE_S)
    aborted = False
    for i, (level, tones, suffix) in enumerate(blocks):
        if i:  # rest between graded blocks
            s.mark("rest", t)
            t += 1.0 if args.test else REST_S
        if level:
            s.mark(f"block_start:{level}", t)
        t, aborted = run_block(s, tones, make_trials(n_std, n_dev, rng.randrange(1 << 30)), t, suffix)
        if aborted:
            break
        if level:
            s.mark(f"block_end:{level}", t)
        if s.wait_until(t):  # wait out the last interval before the next block
            aborted = True
            break
    s.finish(aborted)


if __name__ == "__main__":
    main()
