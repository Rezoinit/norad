import pylsl

from conftest import existing, new_stream

from norad.markers import MarkerOutlet


def test_push_roundtrip():
    before = existing("norad_markers")
    m = MarkerOutlet()
    info = new_stream("norad_markers", before)
    assert info.type() == "Markers"
    inlet = pylsl.StreamInlet(info)
    inlet.open_stream(timeout=2)
    t_sent = m.push("1", "squeeze")
    sample, ts = inlet.pull_sample(timeout=2)
    assert sample == ["1", "squeeze"]
    assert abs(ts + inlet.time_correction() - t_sent) < 0.05
