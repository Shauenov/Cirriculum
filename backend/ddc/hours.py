"""Сценарии распределения часов по темам при неизменной сумме.

Рекомендация формулируется как «рекомендуемое распределение часов по темам внутри раздела
при неизменной недельной нагрузке, основа для КТП учителя». Границы min/max — допущение
(в нормативке пределов не найдено). Отдача по теме калибруется по вариации плановых часов
между классами: gain_t = beta_t * ln(h). Это наблюдательная оценка: если трудным темам
дают больше часов, она смещена (обратная причинность).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .data_io import Dataset
from .panel import build_panel


def _design(panel: pd.DataFrame):
    cols = {}
    cols["loghours"] = np.log(panel.planned_hours.values.astype(float))
    for c in ("prior_z", "school_prior_z"):
        if c in panel:
            cols[c] = panel[c].values
    X = pd.DataFrame(cols, index=panel.index)
    for c in ("textbook_id", "instruction_language", "locality_type", "teacher_experience_band"):
        if c in panel and panel[c].nunique() > 1:
            X = X.join(pd.get_dummies(panel[c], prefix=c, drop_first=True, dtype=float))
    X.insert(0, "const", 1.0)
    return X


def calibrate(panel: pd.DataFrame, topics: list[str]) -> dict[str, float]:
    """beta_t (доля верных на единицу ln часов) для каждой темы, МНК с контролями."""
    out = {}
    for t in topics:
        d = panel[(panel.topic == t) & panel.planned_hours.notna()].dropna(subset=["prior_z"] if "prior_z" in panel else [])
        if len(d) < 50 or d.planned_hours.nunique() < 2:
            out[t] = np.nan
            continue
        X = _design(d)
        beta, *_ = np.linalg.lstsq(X.values, d.pct.values, rcond=None)
        out[t] = float(beta[list(X.columns).index("loghours")])
    return out


def shrink(betas: dict[str, float], ses: dict[str, float], x: dict[str, float] | None = None) -> dict[str, float]:
    """Эмпирико-байесовское сжатие. Цель сжатия — линейная функция сложности темы (мета-регрессия),
    если сложность известна, иначе общее среднее. Отрицательные отдачи обнуляем (отдача неотрицательна)."""
    t = [k for k, v in betas.items() if not np.isnan(v)]
    if not t:
        return {k: 0.0 for k in betas}
    b = np.array([betas[k] for k in t])
    sevals = [v for v in ses.values() if not np.isnan(v)]
    s2 = np.array([(ses.get(k) if not np.isnan(ses.get(k, np.nan)) else np.mean(sevals)) ** 2 for k in t])
    w0 = 1 / (s2 + 1e-9)
    if x and len(t) > 3:
        xv = np.array([x[k] for k in t])
        A = np.column_stack([np.ones(len(t)), xv - xv.mean()])
        coef = np.linalg.solve(A.T @ (A * w0[:, None]), A.T @ (w0 * b))
        mu = A @ coef
        resid = b - mu
        df = max(len(t) - 2, 1)
    else:
        mu = np.full(len(t), np.average(b, weights=w0))
        resid = b - mu
        df = max(len(t) - 1, 1)
    tau2 = max(float(np.sum(resid ** 2) / df - np.mean(s2)), 0.0)
    w = tau2 / (tau2 + s2 + 1e-12)
    sh = mu + w * resid
    out = {k: max(float(v), 0.0) for k, v in zip(t, sh)}
    mean_pos = float(np.mean(list(out.values()))) if out else 0.0
    for k in betas:
        out.setdefault(k, mean_pos)
    return out


def optimize_hours(beta: dict[str, float], current: dict[str, int], lo: dict[str, int], hi: dict[str, int],
                   total: int | None = None) -> dict[str, int]:
    """Жадное распределение целых часов: функция вогнутая, значит жадный алгоритм оптимален.

    Сумма сохраняется точно, границы min/max соблюдаются по построению (без округления)."""
    topics = list(current)
    total = sum(current.values()) if total is None else total
    if sum(lo.values()) > total or sum(hi.values()) < total:
        raise ValueError("Границы несовместимы с суммой часов.")
    h = dict(lo)
    left = total - sum(h.values())
    while left > 0:
        best, gain = None, -1.0
        for t in topics:
            if h[t] >= hi[t]:
                continue
            g = beta[t] * np.log((h[t] + 1) / h[t])
            if g > gain + 1e-15:
                best, gain = t, g
        h[best] += 1
        left -= 1
    return h


def _bounds(cur: dict[str, int], cfg: Config):
    lo = {t: max(cfg.hours_abs_min, int(np.floor(v * cfg.hours_min_factor))) for t, v in cur.items()}
    hi = {t: max(lo[t], int(np.ceil(v * cfg.hours_max_factor))) for t, v in cur.items()}
    return lo, hi


def current_plan(panel: pd.DataFrame, topics: list[str]) -> dict[str, int]:
    """Текущий план = средние плановые часы по классам, округлённые методом наибольших остатков."""
    mean = panel.groupby("topic").planned_hours.mean()
    raw = np.array([mean[t] for t in topics])
    total = int(round(raw.sum()))
    fl = np.floor(raw).astype(int)
    rem = total - fl.sum()
    order = np.argsort(-(raw - fl))
    for i in order[:max(rem, 0)]:
        fl[i] += 1
    return dict(zip(topics, fl.tolist()))


def analyze_hours(ds: Dataset, cfg: Config, difficulty: dict | None = None) -> dict:
    xdiff = {t['topic']: t['difficulty'] for t in difficulty['topics']} if difficulty else None
    if ds.hours is None:
        return dict(available=False, reason="Нет файла hours (плановые часы по темам).")
    panel = build_panel(ds).dropna(subset=["planned_hours"])
    if "prior_z" not in panel:
        return dict(available=False, reason="Нужен файл students с входным уровнем для калибровки отдачи часов.")
    topics = sorted(panel.topic.unique())
    cur = current_plan(panel, topics)
    lo, hi = _bounds(cur, cfg)
    beta_raw = calibrate(panel, topics)

    # бутстреп по школам: SE калибровки, диапазоны часов и прироста
    rng = np.random.default_rng(cfg.seed)
    schools = panel.school_id.unique()
    sidx = {s: i for i, s in enumerate(schools)}
    prep = {}
    for t in topics:   # матрицы строим один раз; бутстреп по школам = взвешенный МНК с кратностями школ
        d = panel[(panel.topic == t) & panel.planned_hours.notna()].dropna(subset=["prior_z"])
        if len(d) < 50 or d.planned_hours.nunique() < 2:
            continue
        X = _design(d)
        prep[t] = (X.values, d.pct.values, d.school_id.map(sidx).values, list(X.columns).index("loghours"))
    boots = []
    for _ in range(cfg.bootstrap_reps):
        mult = np.bincount(rng.integers(0, len(schools), len(schools)), minlength=len(schools)).astype(float)
        row = {}
        for t in topics:
            if t not in prep:
                row[t] = np.nan
                continue
            X, y, g, k = prep[t]
            sw = np.sqrt(mult[g])
            try:   # lstsq устойчив к вырожденным кодировкам, если категория выпала из бутстреп-выборки
                row[t] = float(np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0][k])
            except np.linalg.LinAlgError:
                row[t] = np.nan
        boots.append(row)
    bdf = pd.DataFrame(boots)
    ses = bdf.std(ddof=1).to_dict()
    beta = shrink(beta_raw, ses, xdiff)
    rec = optimize_hours(beta, cur, lo, hi)

    def gain(plan, b):
        return float(sum(b[t] * np.log(plan[t] / cur[t]) for t in topics)) * 100 / len(topics)

    gains, hours_draws, beta_draws = [], [], []
    for _, row in bdf.iterrows():
        b = shrink(row.to_dict(), ses, xdiff)
        beta_draws.append(b)
        p = optimize_hours(b, cur, lo, hi)
        hours_draws.append(p)
        gains.append(gain(rec, b))
    hd = pd.DataFrame(hours_draws)
    a = (1 - cfg.confidence_level) / 2
    g_lo, g_hi = float(np.quantile(gains, a)), float(np.quantile(gains, 1 - a))
    diff_rank = {}
    if difficulty:
        diff_rank = {t["topic"]: t["difficulty"] for t in difficulty["topics"]}
    rows = []
    for t in topics:
        rows.append(dict(topic=t, current=cur[t], recommended=rec[t], delta=rec[t] - cur[t],
                         range=[int(np.quantile(hd[t], a)), int(np.quantile(hd[t], 1 - a))],
                         beta=beta[t], beta_raw=None if np.isnan(beta_raw[t]) else beta_raw[t],
                         beta_se=float(ses.get(t, np.nan)), min=lo[t], max=hi[t],
                         difficulty=diff_rank.get(t)))
    stable = [r for r in rows if r["delta"] != 0 and r["range"][0] <= r["recommended"] <= r["range"][1]]
    return dict(
        available=True, total=int(sum(cur.values())), rows=rows,
        gain_pp=float(gain(rec, beta)), gain_ci=[g_lo, g_hi],
        gain_note=("Ожидаемый прирост средней доли верных (п.п.) при допущениях модели; "
                   "интервал — бутстреп по школам. Если интервал включает 0, выигрыш не доказан."),
        recommendation_text=("Рекомендуемое распределение часов по темам внутри раздела при неизменной недельной "
                             "нагрузке. Основа для календарно-тематического плана учителя; не изменяет перечень "
                             "предметов, недельную нагрузку и цели обучения."),
        assumptions=[
            f"Границы по теме: от {cfg.hours_min_factor:.0%} до {cfg.hours_max_factor:.0%} текущего плана — допущение "
            "проекта, в нормативке пределов не найдено.",
            "Отдача часов калибруется по вариации плановых часов между классами; если трудным темам в школах дают "
            "больше часов, оценка смещена (обратная причинность).",
            "Это сценарий при допущениях, а не «оптимальное решение». Литература даёт малую отдачу часов "
            "(порядка 0,025 SD на дополнительный недельный час для предмета в целом).",
            "Плановые часы ≠ фактические.",
        ],
        method="Калибровка beta_t МНК с контролями → эмпирико-байесовское сжатие к линии «сложность темы → отдача» → жадное целочисленное распределение при фиксированной сумме и границах min/max; бутстреп по школам.",
        n_stable_changes=len(stable),
        _draws=dict(beta=beta, boots=beta_draws, current=cur, lo=lo, hi=hi),
    )


def scenario(draws: dict, plan: dict[str, int], cfg: Config) -> dict:
    """Прогноз для заданного пользователем плана (ползунки): прирост с диапазоном. Сумма должна совпадать."""
    cur = draws["current"]
    topics = list(cur)
    if sum(plan.values()) != sum(cur.values()):
        return dict(error=f"Сумма часов должна оставаться {sum(cur.values())} (сейчас {sum(plan.values())}).")
    if any(plan.get(t, 0) < 1 for t in topics):
        return dict(error="В каждой теме должен быть хотя бы 1 час.")
    out_of_bounds = [t for t in topics if not (draws["lo"][t] <= plan[t] <= draws["hi"][t])]

    def f(b):
        return float(sum(b[t] * np.log(plan[t] / cur[t]) for t in topics)) * 100 / len(topics)
    g = [f(b) for b in draws["boots"]]
    a = (1 - cfg.confidence_level) / 2
    return dict(gain_pp=f(draws["beta"]), gain_ci=[float(np.quantile(g, a)), float(np.quantile(g, 1 - a))],
                out_of_bounds=out_of_bounds)
