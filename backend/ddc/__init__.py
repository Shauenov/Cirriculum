"""Ядро Data-Driven Curriculum. Подхватывает .env (не в git) с необязательными ключами LLM."""
import os
from pathlib import Path


def _load_env():
    for d in (Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[1]):
        f = d / ".env"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    if v.strip():
                        os.environ.setdefault(k.strip(), v.strip())


_load_env()
