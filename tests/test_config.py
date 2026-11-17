from norad.config import Config, load_config, save_config


def test_defaults_when_no_file(tmp_path):
    cfg = load_config(tmp_path / "x.json")
    assert cfg.tobii_ip == "192.168.71.50"
    assert cfg.port == 5500


def test_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    save_config(Config(polar_address="AA:BB"), p)
    assert load_config(p).polar_address == "AA:BB"
