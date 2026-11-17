"""App settings. Defaults here; local overrides in <repo>/settings.json (git-ignored)."""
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = REPO_ROOT / "settings.json"


@dataclass
class Config:
    tobii_ip: str = "192.168.71.50"
    nasal_port: str | None = None
    polar_address: str | None = None
    results_dir: Path = field(default_factory=lambda: REPO_ROOT / "Results")
    port: int = 5500


def load_config(path: Path = SETTINGS_FILE) -> Config:
    if not Path(path).exists():
        return Config()
    data = json.loads(Path(path).read_text())
    known = {f.name for f in fields(Config)}
    cfg = Config(**{k: v for k, v in data.items() if k in known})
    cfg.results_dir = Path(cfg.results_dir)
    return cfg


def save_config(cfg: Config, path: Path = SETTINGS_FILE) -> None:
    data = asdict(cfg)
    data["results_dir"] = str(cfg.results_dir)
    Path(path).write_text(json.dumps(data, indent=2))
