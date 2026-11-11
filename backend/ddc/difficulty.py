"""Сложность тем и качество заданий.

Классические индексы (доля верных, дискриминативность) валидны внутри одной работы
и выборки. Сравнимость заданий из разных работ требует IRT-калибровки с якорными
заданиями — это следующий этап; здесь индекс сложности темы = 1 − средняя доля
верных по «хорошим» заданиям и зависит от набора заданий.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .data_io import Dataset
from .panel import build_panel


def item_stats(ds: Dataset, cfg: Config) -> pd.DataFrame:
    r = ds.results
    m = r.pivot_table(index="student_pseudo_id", columns="task_id", values="score_frac", aggfunc="first")
    total = m.sum(axis=1)
    rows = []
    topic_of = r.drop_duplicates("task_id").set_index("task_id").section_or_topic
    for t in m.columns:
        x = m[t]
        ok = x.notna()
        rest = (total - x.fillna(0))[ok]
        xv = x[ok]
        p = float(xv.mean())
        if xv.std() == 0 or rest.std() == 0:
            disc = float("nan")
        else:
            disc = float(np.corrcoef(xv, rest)[0, 1])
        flags = []
        if np.isnan(disc) or disc < cfg.bad_item_discrimination:
            flags.append("низкая дискриминативность")
        if p < cfg.bad_item_p_low:
            flags.append("почти никто не решил")
        if p > cfg.bad_item_p_high:
            flags.append("почти все решили")
        rows.append(dict(task_id=t, topic=topic_of[t], n=int(ok.sum()), p_correct=p,
                         discrimination=disc, flagged=bool(flags), flags="; ".join(flags)))
    return pd.DataFrame(rows)


def _school_boot_ci(panel: pd.DataFrame, cfg: Config):
    """Интервал для индекса сложности темы: бутстреп по школам (кластеры)."""
    rng = np.random.default_rng(cfg.seed)
    agg = panel.groupby(["school_id", "topic"]).pct.agg(["sum", "count"]).reset_index()
    topics = sorted(panel.topic.unique())
    schools = agg.school_id.unique()
    idx = {t: agg[agg.topic == t].set_index("school_id") for t in topics}
    out = {t: [] for t in topics}
    for _ in range(cfg.bootstrap_reps):
        s = rng.choice(schools, len(schools), replace=True)
        for t in topics:
            d = idx[t].reindex(s).dropna()
            out[t].append(1 - d["sum"].sum() / d["count"].sum())
    a = (1 - cfg.confidence_level) / 2
    return {t: (float(np.quantile(v, a)), float(np.quantile(v, 1 - a))) for t, v in out.items()}


def analyze_difficulty(ds: Dataset, cfg: Config) -> dict:
    items = item_stats(ds, cfg)
    bad = set(items.loc[items.flagged, "task_id"])
    panel_all = build_panel(ds)
    panel = build_panel(ds, exclude_tasks=bad)
    ci = _school_boot_ci(panel, cfg)
    g = panel.groupby("topic").agg(mean_pct=("pct", "mean"), students=("student_pseudo_id", "nunique"),
                                   schools=("school_id", "nunique"))
    g_all = panel_all.groupby("topic").pct.mean()
    nitems = items.groupby("topic").agg(items=("task_id", "count"), flagged=("flagged", "sum"))
    topics = []
    for t, row in g.iterrows():
        enough = row.students >= cfg.min_students_per_topic
        topics.append(dict(
            topic=t, difficulty=float(1 - row.mean_pct), ci=list(ci[t]),
            difficulty_all_items=float(1 - g_all[t]), students=int(row.students), schools=int(row.schools),
            items=int(nitems.loc[t, "items"]), flagged_items=int(nitems.loc[t, "flagged"]),
            status="ok" if enough else "insufficient"))
    topics.sort(key=lambda x: -x["difficulty"])
    for i, t in enumerate(topics, 1):
        t["rank"] = i
    heat_tb = None
    if "textbook_id" in panel:
        h = panel.groupby(["topic", "textbook_id"]).pct.mean().unstack()
        heat_tb = dict(columns=list(h.columns), rows=[dict(topic=t, values=[None if pd.isna(v) else float(v) for v in h.loc[t]])
                                                    for t in [x["topic"] for x in topics]])
    hs = panel.groupby(["school_id", "topic"]).pct.mean().unstack()
    order = [x["topic"] for x in topics]
    heat_school = dict(columns=order, rows=[dict(school=s, values=[None if pd.isna(v) else float(v) for v in hs.loc[s, order]])
                                            for s in hs.index])
    return dict(topics=topics, items=items.round(4).replace({np.nan: None}).to_dict("records"),
                heatmap_textbook=heat_tb, heatmap_school=heat_school,
                method=("Индекс сложности = 1 − средняя доля верных по заданиям без пометки «плохое». "
                        "Интервал — бутстреп по школам. Для сопоставления заданий из разных работ нужна "
                        "IRT-калибровка с якорными заданиями (не реализована)."),
                n_flagged=int(len(bad)))
