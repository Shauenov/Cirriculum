"""Медленная проверка на 15 наборах данных (pytest -m slow)."""
import numpy as np
import pytest
from scipy.stats import spearmanr

from ddc.config import Config
from ddc.difficulty import analyze_difficulty
from ddc.textbooks import analyze_textbooks
from conftest import generate, load_dir, truth
from test_core import true_pp

CFG = Config(bootstrap_reps=20)


@pytest.mark.slow
def test_15_seeds(tmp_path_factory):
    cover = naive_wrong = 0
    rhos = []
    for seed in range(1, 16):
        d = generate(seed, tmp_path_factory.mktemp(f"s{seed}"))
        ds = load_dir(d)
        tb = analyze_textbooks(ds, CFG)
        tr = true_pp(d, ds)
        comp = {c["textbook"]: c for c in tb["comparisons"]}
        cover += all(comp[t]["ci"][0] <= tr[t] <= comp[t]["ci"][1] for t in "AC")
        best_naive = max(comp, key=lambda t: comp[t]["naive_diff"])
        naive_wrong += (comp["A"]["naive_diff"] > 0 > tr["A"]) or best_naive != "C"
        diff = analyze_difficulty(ds, CFG)
        est = {t["topic"]: t["difficulty"] for t in diff["topics"]}
        names = ds.items.drop_duplicates("topic_id").set_index("section_or_topic").topic_id
        tt = truth(d)["topic_difficulty"]
        rhos.append(spearmanr([est[n] for n in names.index], [tt[names[n]] for n in names.index]).statistic)
    print(f"COVERAGE {cover}/15  NAIVE_WRONG {naive_wrong}/15  RHO mean={np.mean(rhos):.2f} min={min(rhos):.2f}")
    assert cover >= 13           # номинал 95%; с t-интервалами и малым числом школ ждём почти все
    assert np.mean(rhos) >= 0.8 and min(rhos) >= 0.65
