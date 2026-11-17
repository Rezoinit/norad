import importlib.util
from collections import Counter
from pathlib import Path

import numpy as np

TASK = Path(__file__).resolve().parent.parent / "tasks" / "digit_span" / "digit_span.py"
spec = importlib.util.spec_from_file_location("digit_span", TASK)
ds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds)  # must not need PsychoPy to import


def test_levels():
    assert ds.LEVELS == {"easy": 3, "medium": 5, "hard": 7}


def test_default_is_easy_only():
    trials = ds.make_trials(graded=False, seed=1)
    assert len(trials) == 16 and {lvl for lvl, _ in trials} == {"easy"}
    assert all(len(d) == 3 for _, d in trials)


def test_graded_mixed_8_per_level():
    trials = ds.make_trials(graded=True, seed=1)
    assert Counter(lvl for lvl, _ in trials) == {"easy": 8, "medium": 8, "hard": 8}
    assert all(len(d) == ds.LEVELS[lvl] for lvl, d in trials)
    levels = [lvl for lvl, _ in trials]
    assert levels != sorted(levels, key=list(ds.LEVELS).index)  # mixed, not in blocks


def test_digits_never_repeat_within_a_trial():
    for _, digits in ds.make_trials(graded=True, seed=2):
        assert len(set(digits)) == len(digits) and all(0 <= d <= 9 for d in digits)


def test_seed_repeats():
    assert ds.make_trials(True, seed=3) == ds.make_trials(True, seed=3)


def test_score():
    assert ds.score("357", [3, 5, 7])
    assert ds.score(" 3 5 7 ", [3, 5, 7])
    assert not ds.score("375", [3, 5, 7])
    assert not ds.score("35", [3, 5, 7])


def test_trim_silence():
    fs = 1000
    x = np.zeros(1000)
    x[200:500] = 0.5 * np.sin(np.arange(300))  # speech from 0.2 to 0.5 s
    y = ds.trim_silence(x, fs)
    assert 290 <= len(y) <= 320  # leading and trailing silence removed (5 ms margin each side)
