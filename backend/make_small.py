"""Маленький резервный набор «на случай сбоя»: 28 случайных школ из основного."""
from pathlib import Path

import numpy as np
import pandas as pd

d = Path(__file__).parent / "demo_data"
o = d / "small"
o.mkdir(exist_ok=True)
sch = pd.read_csv(d / "schools.csv")
keep = set(np.random.default_rng(7).choice(sch.school_id, 28, replace=False))
for f in ["schools", "students", "teaching", "hours"]:
    x = pd.read_csv(d / f"{f}.csv")
    x[x.school_id.isin(keep)].to_csv(o / f"{f}.csv", index=False)
pd.read_csv(d / "items.csv").to_csv(o / "items.csv", index=False)
r = pd.read_csv(d / "results_long.csv")
r[r.school_id.isin(keep)].to_csv(o / "results_long.csv", index=False)
print(len(keep), (o / "results_long.csv").stat().st_size / 1e6, "MB")
