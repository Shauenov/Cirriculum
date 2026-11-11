"""Эксперимент: как связь «трудным темам дают больше часов» ломает калибровку отдачи часов,
и какой вариант оптимизатора устойчивее.

Для каждого уровня связи (tilt) и seed генерируем данные, строим рекомендацию несколькими вариантами и
оцениваем её по ИСТИННОЙ модели (ground_truth читается только в этом валидационном скрипте):
  share = (истинный выигрыш рекомендации) / (истинный выигрыш оптимума при тех же границах);
  1 = как оптимум, 0 = как текущий план, < 0 = хуже текущего плана.
Результат: validation_hours.json.
"""
import json
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from ddc.config import Config  # noqa: E402
from ddc.data_io import build_dataset  # noqa: E402
from ddc.difficulty import analyze_difficulty  # noqa: E402
from ddc.hours import _bounds, analyze_hours  # noqa: E402

GEN = ROOT / "synthetic_dc" / "code" / "generate_data.py"
sig = lambda x: 1 / (1 + np.exp(-x))  # noqa: E731
VARIANTS = {
    "eb": dict(),                                   # сжатие эмпирическим Байесом (по умолчанию)
    "pooled": dict(hours_pool=True),                # полное сжатие к линии «сложность → отдача»
    "pooled_step1": dict(hours_pool=True, hours_max_step=1),
}


def run(tilt, seed, reps=60):
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([sys.executable, str(GEN), "--seed", str(seed), "--out", td,
                        "--hours-follow-difficulty", str(tilt)], check=True, capture_output=True)
        files = {p.name: p.read_bytes() for p in Path(td).glob("*.csv")}
        truth = json.loads((Path(td) / "ground_truth.json").read_text(encoding="utf-8"))
    ds = build_dataset(files, synthetic=True)
    base_cfg = Config(bootstrap_reps=reps)
    d = analyze_difficulty(ds, base_cfg)
    name2id = ds.items.drop_duplicates("topic_id").set_index("section_or_topic").topic_id
    grid = np.random.default_rng(0).normal(0, 1, 2000)
    a, b, g = truth["task_discrimination"], truth["task_difficulty"], truth["hours_gamma"]
    by_topic = ds.items.groupby("topic_id").task_id.apply(list)
    out = []
    for name, kw in VARIANTS.items():
        cfg = replace(base_cfg, **kw)
        h = analyze_hours(ds, cfg, d)
        cur = {name2id[r["topic"]]: r["current"] for r in h["rows"]}
        rec = {name2id[r["topic"]]: r["recommended"] for r in h["rows"]}
        lo, hi = _bounds(cur, cfg)

        def tv(t, hh):
            eff = g[t] * np.log(hh / cur[t])
            return np.mean([sig(a[k] * (grid + eff - b[k])).mean() for k in by_topic[t]])

        def total(plan):
            return np.mean([tv(t, plan[t]) for t in plan]) * 100
        opt = dict(lo)
        left = sum(cur.values()) - sum(opt.values())
        while left > 0:
            best = max((t for t in opt if opt[t] < hi[t]), key=lambda t: tv(t, opt[t] + 1) - tv(t, opt[t]))
            opt[best] += 1
            left -= 1
        v0, vr, vo = total(cur), total(rec), total(opt)
        out.append(dict(variant=name, tilt=tilt, seed=seed, gain_true_pp=float(vr - v0), optimum_true_pp=float(vo - v0),
                        share=float((vr - v0) / (vo - v0)) if vo > v0 + 1e-9 else None,
                        moved=int(sum(abs(rec[t] - cur[t]) for t in cur) // 2),
                        ci_includes_zero=bool(h["gain_ci"][0] <= 0 <= h["gain_ci"][1])))
    return out


if __name__ == "__main__":
    allr = []
    for tilt in (0.0, 0.5, 1.0):
        for seed in (1, 2, 3, 4, 5):
            allr += run(tilt, seed)
            print(tilt, seed, flush=True)
    (Path(__file__).parent / "validation_hours.json").write_text(json.dumps(allr, indent=1), encoding="utf-8")
    for v in VARIANTS:
        for tilt in (0.0, 0.5, 1.0):
            rows = [r for r in allr if r["variant"] == v and r["tilt"] == tilt]
            print(f"{v:13s} tilt={tilt}: true gain {np.mean([r['gain_true_pp'] for r in rows]):+.3f} pp "
                  f"(optimum {np.mean([r['optimum_true_pp'] for r in rows]):+.3f}), "
                  f"worse than current in {sum(r['gain_true_pp'] < 0 for r in rows)}/5, CI∋0 {sum(r['ci_includes_zero'] for r in rows)}/5")
