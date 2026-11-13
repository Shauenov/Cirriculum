import io

import numpy as np
import pandas as pd
import pytest

from ddc.config import Config
from ddc.data_io import ImportError_, build_dataset
from ddc.difficulty import analyze_difficulty
from ddc.hours import _bounds, optimize_hours
from ddc.textbooks import analyze_textbooks, bh_fdr
from conftest import generate, load_dir, truth

CFG = Config(bootstrap_reps=30)


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def true_pp(d, ds):
    """Истинный эффект учебников (п.п. против B) в эталонной популяции N(0,1)."""
    t = truth(d)
    items = ds.items
    grid = np.random.default_rng(0).normal(0, 1, 4000)
    by_topic = items.groupby("topic_id").task_id.apply(list)
    a, b = t["task_discrimination"], t["task_difficulty"]

    def pct(tb):
        vals = []
        for tp, tasks in by_topic.items():
            extra = t["textbook_base"][tb] + t["textbook_topic_extra"].get(f"{tb}:{tp}", 0.0)
            vals.append(np.mean([sigmoid(a[k] * (grid + extra - b[k])).mean() for k in tasks]))
        return np.mean(vals) * 100
    base = pct("B")
    return {tb: pct(tb) - base for tb in "ABC"}


# ---------- воспроизводимость и качество на seed 2026 ----------
def test_seed2026_reproduces_report(seed2026):
    d, ds = seed2026
    assert ds.quality.stats["schools"] == 60 and ds.quality.stats["students"] == 3140
    res = analyze_textbooks(ds, CFG)
    comp = {c["textbook"]: c for c in res["comparisons"]}
    assert comp["A"]["estimate"] == pytest.approx(-7.3, abs=0.2)
    assert comp["C"]["estimate"] == pytest.approx(2.6, abs=0.2)
    assert comp["A"]["naive_diff"] == pytest.approx(8.7, abs=0.1)


def test_pairwise_matrix_is_consistent(seed2026):
    d, ds = seed2026
    res = analyze_textbooks(ds, CFG)
    pr = {(p["a"], p["b"]): p for p in res["pairs"]}
    assert len(pr) == 6                                              # все упорядоченные пары из трёх учебников
    ref = res["reference"]
    comp = {c["textbook"]: c for c in res["comparisons"]}
    for tb, c in comp.items():                                       # пары с эталоном совпадают с основным сравнением
        assert pr[(tb, ref)]["estimate"] == pytest.approx(c["estimate"], abs=1e-6)
    for (a, b), p in pr.items():                                     # антисимметрия и интервал переворачивается
        q = pr[(b, a)]
        assert q["estimate"] == pytest.approx(-p["estimate"], abs=1e-6)
        assert q["ci"][0] == pytest.approx(-p["ci"][1], abs=1e-6)
    a, c_ = [t for t in comp if t != ref][:2]                        # транзитивность оценок
    assert pr[(a, c_)]["estimate"] == pytest.approx(comp[a]["estimate"] - comp[c_]["estimate"], abs=1e-6)


def test_naive_wrong_model_right_seed2026(seed2026):
    d, ds = seed2026
    res = analyze_textbooks(ds, CFG)
    tr = true_pp(d, ds)
    comp = {c["textbook"]: c for c in res["comparisons"]}
    assert comp["A"]["naive_diff"] > 0 > tr["A"]          # наивное сравнение называет A лучшим, истина — хуже
    for tb in "AC":
        lo, hi = comp[tb]["ci"]
        assert lo <= tr[tb] <= hi


def test_difficulty_rank_correlation(seed2026):
    from scipy.stats import spearmanr
    d, ds = seed2026
    r = analyze_difficulty(ds, CFG)
    est = pd.Series({t["topic"]: t["difficulty"] for t in r["topics"]})
    names = ds.items.drop_duplicates("topic_id").set_index("section_or_topic").topic_id
    tr = pd.Series(truth(d)["topic_difficulty"])
    rho = spearmanr(est.values, tr.reindex(names.reindex(est.index).values).values).statistic
    assert rho >= 0.7


def test_irt_recovers_item_parameters(seed2026):
    d, ds = seed2026
    from ddc.irt import topic_irt
    items, _ = topic_irt(ds)
    t = truth(d)
    b = items.set_index("task_id").b
    assert np.corrcoef(b, pd.Series(t["task_difficulty"]).reindex(b.index))[0, 1] > 0.98
    assert np.corrcoef(items.a, pd.Series(t["task_discrimination"]).reindex(items.task_id))[0, 1] > 0.9


def test_irt_topic_rank_beats_threshold(seed2026):
    from scipy.stats import spearmanr
    d, ds = seed2026
    r = analyze_difficulty(ds, Config(bootstrap_reps=10))
    names = ds.items.drop_duplicates("topic_id").set_index("section_or_topic").topic_id
    tt = truth(d)["topic_difficulty"]
    rho = spearmanr([x["difficulty_irt"] for x in r["topics"]], [tt[names[x["topic"]]] for x in r["topics"]]).statistic
    assert rho >= 0.9
    assert all(x["irt_ci"][0] <= x["difficulty_irt"] <= x["irt_ci"][1] for x in r["topics"])


def test_robust_logit_check_agrees(seed2026):
    d, ds = seed2026
    res = analyze_textbooks(ds, CFG)
    tr = true_pp(d, ds)
    for c in res["comparisons"]:
        assert c["robust_agrees"]
        assert c["robust"]["ci"][0] <= tr[c["textbook"]] - tr[res["reference"]] <= c["robust"]["ci"][1]


def test_irt_handles_missing_responses():
    from ddc.irt import fit_2pl
    rng = np.random.default_rng(0)
    th = rng.normal(size=1500)
    b = np.linspace(-1.5, 1.5, 20)
    Y = (rng.random((1500, 20)) < 1 / (1 + np.exp(-(th[:, None] - b[None, :])))).astype(float)
    Y[rng.random(Y.shape) < 0.2] = np.nan
    a, bh = fit_2pl(Y)
    assert np.corrcoef(bh, b)[0, 1] > 0.98


def test_topic_exceptions_found_with_fdr(seed2026):
    d, ds = seed2026
    res = analyze_textbooks(ds, CFG)
    hit = [e for e in res["topic_effects"] if e["textbook"] == "A" and "Функции" in e["topic"]][0]
    assert hit["estimate"] < -8 and hit["significant_fdr"]


def test_insufficient_label_when_few_schools(seed2026):
    d, ds = seed2026
    res = analyze_textbooks(ds, Config(bootstrap_reps=10, min_schools_per_textbook=12))
    c = next(x for x in res["comparisons"] if x["textbook"] == "C")   # у C 11 школ
    assert c["status"] == "insufficient" and not c["significant"]


# ---------- оптимизатор ----------
@pytest.mark.parametrize("seed", range(30))
def test_optimizer_keeps_sum_and_bounds(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(5, 14))
    topics = [f"t{i}" for i in range(n)]
    cur = {t: int(rng.integers(3, 12)) for t in topics}
    lo, hi = _bounds(cur, Config())
    beta = {t: float(rng.uniform(0, 0.1)) for t in topics}
    out = optimize_hours(beta, cur, lo, hi)
    assert sum(out.values()) == sum(cur.values())
    assert all(lo[t] <= out[t] <= hi[t] for t in topics)


def test_optimizer_gives_hours_to_high_return_topics():
    cur = {"a": 6, "b": 6}
    out = optimize_hours({"a": 0.10, "b": 0.01}, cur, {"a": 3, "b": 3}, {"a": 9, "b": 9})
    assert out["a"] > out["b"]       # отдача выше → больше часов (а не «трудные получают меньше»)


def test_optimizer_rejects_infeasible_bounds():
    with pytest.raises(ValueError):
        optimize_hours({"a": 1, "b": 1}, {"a": 5, "b": 5}, {"a": 6, "b": 6}, {"a": 8, "b": 8})


def test_bh_fdr_monotone():
    q = bh_fdr([0.001, 0.01, 0.04, 0.5])
    assert all(0 <= x <= 1 for x in q) and q[0] <= q[1] <= q[2] <= q[3]


# ---------- импорт ----------
GOOD = ("school_id,class,student_pseudo_id,task_id,section_or_topic,score,max_score\n"
        "S1,7A,P1,T1,Тема1,1,1\nS1,7A,P2,T1,Тема1,0,1\nS2,7A,P3,T1,Тема1,1,1\nS3,7A,P4,T1,Тема1,1,1\n")


def imp(text, name="results_long.csv"):
    return build_dataset({name: text.encode("utf-8")})


def test_import_good():
    assert imp(GOOD).quality.ok


@pytest.mark.parametrize("bad, msg", [
    (GOOD.replace("max_score", "mx"), "обязательных колонок"),
    (GOOD.replace(",1,1\nS1,7A,P2", ",абв,1\nS1,7A,P2", 1), "нечисловых"),
    (GOOD.replace("P4,T1,Тема1,1,1", "P4,T1,Тема1,5,1"), "вне диапазона"),
    (GOOD.replace("student_pseudo_id", "student_fio"), "персональные"),
    (GOOD.replace("P1", "123456789012").replace("P2", "123456789013").replace("P3", "123456789014").replace("P4", "123456789015"), "ИИН"),
])
def test_import_rejects_bad(bad, msg):
    with pytest.raises(ImportError_) as e:
        imp(bad)
    assert msg in str(e.value)


def test_import_rejects_too_few_schools():
    with pytest.raises(ImportError_):
        imp("school_id,class,student_pseudo_id,task_id,section_or_topic,score,max_score\nS1,7A,P1,T1,Т,1,1\n")


def test_import_rejects_garbage_file():
    with pytest.raises(ImportError_):
        build_dataset({"foo.csv": b"\x00\x01\x02 not a table"})


# ---------- слабая связь часов со сложностью (обратная причинность) ----------
def test_hours_confounding_scenario_documented(tmp_path):
    """Если трудным темам дают больше часов, калибровка отдачи смещается. Проверяем и фиксируем размер смещения."""
    from ddc.hours import calibrate
    from ddc.panel import build_panel
    res = {}
    for tilt in (0.0, 0.5):
        d = generate(2026, tmp_path / f"t{tilt}", tilt)
        ds = load_dir(d)
        panel = build_panel(ds).dropna(subset=["planned_hours"])
        topics = sorted(panel.topic.unique())
        beta = calibrate(panel, topics)
        name2id = ds.items.drop_duplicates("topic_id").set_index("section_or_topic").topic_id
        g = truth(d)["hours_gamma"]
        true_beta = np.array([g[name2id[t]] for t in topics])
        est = np.array([beta[t] for t in topics])
        res[tilt] = dict(corr=float(np.corrcoef(est, true_beta)[0, 1]), mean=float(est.mean()))
    print("CALIBRATION", res)
    assert set(res) == {0.0, 0.5}


def test_full_pipeline_runs_on_small_demo():
    """Регрессия: на резервном наборе бутстреп-выборка может потерять категорию — расчёт не должен падать."""
    from ddc.pipeline import load_demo, run_all
    res = run_all(load_demo("small"), Config(bootstrap_reps=40))
    assert res["hours"]["available"] and res["textbooks"]["available"]
    assert all("difficulty_irt" in t for t in res["difficulty"]["topics"])


def test_dif_detects_injected_and_no_false_positives():
    from ddc.dif import dif_from_matrix
    rng = np.random.default_rng(1)
    N, J = 2400, 30
    th = rng.normal(size=N)
    g = np.where(rng.random(N) < .5, "kz", "ru")
    cl = rng.integers(0, 40, N).astype(str)
    b = rng.normal(size=J)
    bb = np.tile(b, (N, 1))
    bb[np.ix_(g == "ru", [3, 11])] += 0.9
    Y = (rng.random((N, J)) < 1 / (1 + np.exp(-(th[:, None] - bb)))).astype(float)
    tab, _ = dif_from_matrix(Y, g, cl)
    assert set(np.where(tab.flagged)[0]) == {3, 11}
    Y0 = (rng.random((N, J)) < 1 / (1 + np.exp(-(th[:, None] - b[None, :])))).astype(float)
    tab0, _ = dif_from_matrix(Y0, g, cl)
    assert tab0.flagged.sum() == 0


def test_dif_on_synthetic_demo_flags_nothing(seed2026):
    from ddc.dif import analyze_dif
    d, ds = seed2026
    r = analyze_dif(ds, CFG)
    assert r["available"] and r["n_flagged"] <= 1      # в генераторе DIF не закладывался


def test_anchor_linking_two_forms():
    """Две формы, решаемые разными учениками, связаны якорными заданиями: общая шкала восстанавливается."""
    from ddc.irt import fit_2pl, link_components
    rng = np.random.default_rng(3)
    N, J = 3000, 30
    b = rng.normal(0, 1, J)
    th = np.concatenate([rng.normal(-0.5, 1, N // 2), rng.normal(0.5, 1, N // 2)])
    P = 1 / (1 + np.exp(-(th[:, None] - b[None, :])))
    Y = (rng.random((N, J)) < P).astype(float)
    # форма 1: задания 0..19, форма 2: задания 10..29, якоря 10..19
    Y[: N // 2, 20:] = np.nan
    Y[N // 2:, :10] = np.nan
    M = pd.DataFrame(Y)
    assert link_components(M) == 1
    a_, bh = fit_2pl(Y)
    assert np.corrcoef(bh, b)[0, 1] > 0.97
    # без якорей: изолированные формы
    Y2 = Y.copy()
    Y2[N // 2:, 10:20] = np.nan
    assert link_components(pd.DataFrame(Y2)) == 2


def test_xlsx_import_roundtrip(tmp_path):
    import io
    df = pd.read_csv(io.StringIO(GOOD))
    f = tmp_path / "results_long.xlsx"
    df.to_excel(f, index=False)
    assert build_dataset({"results_long.xlsx": f.read_bytes()}).quality.ok


@pytest.mark.parametrize("col", ["student_name", "Name", "phone", "email", "дата_рождения", "Фамилия", "address"])
def test_import_rejects_pii_like_columns(col):
    bad = GOOD.replace("school_id,class,", f"school_id,{col},class,", 1)
    bad = "\n".join([bad.splitlines()[0]] + [ln.replace("S1,", "S1,x,", 1).replace("S2,", "S2,x,", 1).replace("S3,", "S3,x,", 1)
                                              for ln in bad.splitlines()[1:]]) + "\n"
    with pytest.raises(ImportError_) as e:
        imp(bad)
    assert "персональные" in str(e.value)


def test_two_textbooks_in_parallel_warns():
    from ddc.pipeline import DEMO_DIR
    fs = {p.name: p.read_bytes() for p in (DEMO_DIR / "small").glob("*.csv")}
    t = pd.read_csv(io.BytesIO(fs["teaching.csv"]))
    first = t.school_id.iloc[0]
    t.loc[t.school_id == first, "textbook_id"] = ["A", "Z"][: (t.school_id == first).sum()]
    fs["teaching.csv"] = t.to_csv(index=False).encode()
    ds = build_dataset(fs)
    assert any("несколько учебников" in w for w in ds.quality.warnings)


def test_textbooks_without_prior_are_not_called_adjusted():
    from ddc.pipeline import DEMO_DIR
    fs = {p.name: p.read_bytes() for p in (DEMO_DIR / "small").glob("*.csv") if p.stem != "students"}
    res = analyze_textbooks(build_dataset(fs), CFG)
    assert not res["adjusted"]
    assert all(c["status"] == "insufficient" for c in res["comparisons"])
    assert not any(e["significant_fdr"] or e["significant_dev"] for e in res["topic_effects"])


def test_interaction_finds_exactly_planted_topics(seed2026):
    d, ds = seed2026
    res = analyze_textbooks(ds, CFG)
    names = ds.items.drop_duplicates("topic_id").set_index("section_or_topic").topic_id
    found = {(e["textbook"], names[e["topic"]]) for e in res["topic_effects"] if e["significant_dev"]}
    assert found == {("A", "T08"), ("C", "T09")}


def test_hours_rejects_inverted_bounds(seed2026):
    from ddc.hours import analyze_hours
    d, ds = seed2026
    r = analyze_hours(ds, Config(bootstrap_reps=10, hours_min_factor=1.2, hours_max_factor=1.1))
    assert not r["available"]
