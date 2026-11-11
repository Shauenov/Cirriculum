from pathlib import Path

from .config import Config
from .data_io import build_dataset
from .dif import analyze_dif
from .difficulty import analyze_difficulty
from .hours import analyze_hours
from .textbooks import analyze_textbooks

DEMO_DIR = Path(__file__).resolve().parents[1] / "demo_data"


def load_demo(subdir: str = "") -> "Dataset":  # noqa: F821
    d = DEMO_DIR / subdir if subdir else DEMO_DIR
    files = {p.name: p.read_bytes() for p in d.glob("*.csv")}
    return build_dataset(files, synthetic=True)


def run_all(ds, cfg: Config | None = None) -> dict:
    cfg = cfg or Config()
    diff = analyze_difficulty(ds, cfg)
    tb = analyze_textbooks(ds, cfg)
    hours = analyze_hours(ds, cfg, diff)
    return dict(quality=ds.quality.to_dict(), synthetic=ds.synthetic, config=cfg.to_dict(),
                difficulty=diff, textbooks=tb, hours=hours, dif=analyze_dif(ds, cfg))
