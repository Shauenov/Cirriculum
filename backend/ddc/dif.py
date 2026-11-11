"""Дифференциальное функционирование заданий (DIF) между языками обучения.

Зачем: «слабая тема» может оказаться артефактом перевода (формулировка на казахском или русском).
Метод: 2PL отдельно по группам, шкалы выравниваются по медиане b (Mean/Median linking, устойчив к
нескольким DIF-заданиям), Δb по заданию, интервал — бутстреп по школам, контроль FDR (Бенджамини–Хохберг).
Задание помечается, если FDR-значимо и |Δb| ≥ порога (практическая значимость).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .irt import fit_2pl
from .textbooks import bh_fdr


def dif_from_matrix(Y: np.ndarray, group: np.ndarray, cluster: np.ndarray, reps: int = 40, seed: int = 2026,
                    min_delta: float = 0.5, alpha: float = 0.05):
    """Y: N×J, group: метка группы (две), cluster: школа. Возвращает таблицу Δb по заданиям."""
    labs = sorted(set(group))
    assert len(labs) == 2
    idx = [np.where(group == g)[0] for g in labs]

    def fit(rows_a, rows_b, init=None, n_iter=40):
        res = []
        for rows, i0 in zip((rows_a, rows_b), init or (None, None)):
            res.append(fit_2pl(Y[rows], n_iter=n_iter, init=i0))
        d = res[1][1] - res[0][1]
        return res, d - np.median(d)

    base, delta = fit(*idx)
    rng = np.random.default_rng(seed)
    clusters = np.unique(cluster)
    rows_c = {c: np.where(cluster == c)[0] for c in clusters}
    draws = []
    for _ in range(reps):
        pick = rng.choice(clusters, len(clusters), replace=True)
        rows = np.concatenate([rows_c[c] for c in pick])
        ra = rows[group[rows] == labs[0]]
        rb = rows[group[rows] == labs[1]]
        if len(ra) < 50 or len(rb) < 50:
            continue
        _, d = fit(ra, rb, init=base, n_iter=8)
        draws.append(d)
    D = np.array(draws)
    se = D.std(axis=0, ddof=1)
    z = delta / np.where(se > 0, se, np.nan)
    from scipy.stats import norm
    p = 2 * (1 - norm.cdf(np.abs(np.nan_to_num(z))))
    q = np.array(bh_fdr(p.tolist()))
    flagged = (q < alpha) & (np.abs(delta) >= min_delta)
    return pd.DataFrame(dict(delta_b=delta, se=se, q=q, flagged=flagged)), labs


def analyze_dif(ds, cfg: Config) -> dict:
    if ds.schools is None or "instruction_language" not in ds.schools.columns:
        return dict(available=False, reason="Нет колонки instruction_language в schools.")
    r = ds.results
    M = r.pivot_table(index="student_pseudo_id", columns="task_id", values="score_frac", aggfunc="first")
    st = r.drop_duplicates("student_pseudo_id").set_index("student_pseudo_id").school_id.reindex(M.index)
    lang = st.map(ds.schools.set_index("school_id").instruction_language)
    ok = lang.notna().values
    if len(set(lang[ok])) != 2 or min(lang[ok].value_counts()) < 200:
        return dict(available=False, reason="Нужны две группы по языку обучения, не менее 200 учеников в каждой.")
    tab, labs = dif_from_matrix(M.values[ok], lang.values[ok].astype(str), st.values[ok].astype(str),
                                reps=40, seed=cfg.seed)
    topic_of = r.drop_duplicates("task_id").set_index("task_id").section_or_topic.reindex(M.columns).values
    tab["task_id"] = M.columns
    tab["topic"] = topic_of
    flagged = tab[tab.flagged]
    by_topic = tab.groupby("topic").delta_b.mean()
    return dict(
        available=True, groups=labs, n_flagged=int(len(flagged)), n_items=int(len(tab)),
        flagged=flagged.round(3).to_dict("records"),
        topic_shift={k: float(v) for k, v in by_topic.items()},
        note=(f"Δb = сложность в группе «{labs[1]}» минус «{labs[0]}» (логиты, после выравнивания шкал по медиане). "
              "Помеченные задания стоит проверить на качество перевода; тема не должна считаться «слабой» "
              "только из-за них. Метод проверен на симуляции, на реальных данных нужна экспертная проверка."),
    )
