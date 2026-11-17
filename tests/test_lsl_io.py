from pylsl import StreamInlet

from norad.lsl_io import channel_labels, find_streams, make_outlet


def test_outlet_roundtrip():
    out = make_outlet("norad_test_io", ["a", "b"], 100)
    infos = [i for i in find_streams(wait=1.0) if i.name() == "norad_test_io"]
    assert infos
    inlet = StreamInlet(infos[0])
    assert channel_labels(inlet.info(timeout=2)) == ["a", "b"]
    inlet.open_stream(timeout=2)
    out.push_sample([1, 2])
    sample, _ = inlet.pull_sample(timeout=2)
    assert sample == [1, 2]
