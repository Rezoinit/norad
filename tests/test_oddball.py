import importlib.util
from pathlib import Path

ODDBALL = Path(__file__).resolve().parent.parent / "tasks" / "oddball" / "oddball.py"
spec = importlib.util.spec_from_file_location("oddball", ODDBALL)
oddball = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oddball)  # must not need PsychoPy to import


def test_counts_and_order_rules():
    trials = oddball.make_trials(120, 30, seed=1)
    tones = [t for t, _ in trials]
    assert tones.count("standard") == 120 and tones.count("deviant") == 30
    assert all(t == "standard" for t in tones[:5])  # lead-in
    assert not any(a == b == "deviant" for a, b in zip(tones, tones[1:]))  # never two deviants in a row


def test_intervals_jittered_in_range():
    soas = [s for _, s in oddball.make_trials(120, 30, seed=2)]
    assert all(1.5 <= s <= 2.5 for s in soas)
    assert max(soas) - min(soas) > 0.5


def test_seed_repeats_and_differs():
    assert oddball.make_trials(20, 4, seed=3) == oddball.make_trials(20, 4, seed=3)
    assert oddball.make_trials(20, 4, seed=3) != oddball.make_trials(20, 4, seed=4)
