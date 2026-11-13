"""Маленький набор для показа загрузки своих файлов: 14 школ из основного демо-набора.
Лёгкий (быстро считается), содержит все шесть файлов, никаких персональных данных.
Запуск: python make_sample_upload.py  ->  ../sample_upload/"""
from pathlib import Path

import numpy as np
import pandas as pd

d = Path(__file__).parent / "demo_data"
o = Path(__file__).parent.parent / "sample_upload"
o.mkdir(exist_ok=True)
sch = pd.read_csv(d / "schools.csv")
tch = pd.read_csv(d / "teaching.csv")
rng = np.random.default_rng(11)
# по 4–5 школ на каждый учебник, чтобы сравнение имело смысл
keep = set()
for tb, g in tch.groupby("textbook_id"):
    ids = sorted(set(g.school_id))
    keep |= set(rng.choice(ids, min(5, len(ids)), replace=False))
for f in ["schools", "students", "teaching", "hours"]:
    x = pd.read_csv(d / f"{f}.csv")
    x[x.school_id.isin(keep)].to_csv(o / f"{f}.csv", index=False)
pd.read_csv(d / "items.csv").to_csv(o / "items.csv", index=False)
r = pd.read_csv(d / "results_long.csv")
r[r.school_id.isin(keep)].to_csv(o / "results_long.csv", index=False)
print(len(keep), "школ;", round((o / "results_long.csv").stat().st_size / 1e6, 1), "MB")
