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
    cover = naive_wrong = rcover = 0
    rhos, irt_rhos = [], []
    for seed in range(1, 16):
        d = generate(seed, tmp_path_factory.mktemp(f"s{seed}"))
        ds = load_dir(d)
        tb = analyze_textbooks(ds, CFG)
        tr = true_pp(d, ds)
        ref = tb["reference"]
        comp = {c["textbook"]: c for c in tb["comparisons"]}
        rel = {t: tr[t] - tr[ref] for t in comp}
        cover += all(comp[t]["ci"][0] <= rel[t] <= comp[t]["ci"][1] for t in comp)
        rcover += all(comp[t]["robust"]["ci"][0] <= rel[t] <= comp[t]["robust"]["ci"][1] for t in comp)
        naive_means = {r["textbook"]: r["naive_mean"] for r in tb["table"]}
        naive_wrong += max(naive_means, key=naive_means.get) != max(tr, key=tr.get)
        diff = analyze_difficulty(ds, CFG)
        est = {t["topic"]: t["difficulty"] for t in diff["topics"]}
        names = ds.items.drop_duplicates("topic_id").set_index("section_or_topic").topic_id
        tt = truth(d)["topic_difficulty"]
        irt = {x["topic"]: x["difficulty_irt"] for x in diff["topics"]}
        irt_rhos.append(spearmanr([irt[n] for n in names.index], [tt[names[n]] for n in names.index]).statistic)
        rhos.append(spearmanr([est[n] for n in names.index], [tt[names[n]] for n in names.index]).statistic)
    print(f"ROBUST_COVERAGE {rcover}/15  IRT_RHO mean={np.mean(irt_rhos):.2f} min={min(irt_rhos):.2f}")
    print(f"COVERAGE {cover}/15  NAIVE_WRONG {naive_wrong}/15  RHO mean={np.mean(rhos):.2f} min={min(rhos):.2f}")
    assert cover >= 13           # номинал 95%; с t-интервалами и малым числом школ ждём почти все
    assert np.mean(irt_rhos) >= 0.85 and min(irt_rhos) >= 0.7 and rcover >= 13
    assert np.mean(rhos) >= 0.8 and min(rhos) >= 0.65
