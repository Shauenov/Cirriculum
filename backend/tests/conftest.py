import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "synthetic_dc" / "code" / "generate_data.py"
sys.path.insert(0, str(ROOT / "backend"))


def generate(seed: int, out: Path, tilt: float = 0.0) -> Path:
    if not (out / "results_long.csv").exists():
        subprocess.run([sys.executable, str(GEN), "--seed", str(seed), "--out", str(out),
                        "--hours-follow-difficulty", str(tilt)], check=True, capture_output=True)
    return out


def load_dir(d: Path):
    from ddc.data_io import build_dataset
    files = {p.name: p.read_bytes() for p in d.glob("*.csv")}
    return build_dataset(files, synthetic=True)


def truth(d: Path) -> dict:
    """Истина читается только в тестах и блоке валидации, не аналитическими модулями."""
    return json.loads((d / "ground_truth.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def seed2026(tmp_path_factory):
    d = generate(2026, tmp_path_factory.mktemp("s2026"))
    return d, load_dir(d)
