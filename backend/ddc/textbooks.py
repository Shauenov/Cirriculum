"""Сравнение учебников: наивное и с поправкой на контекст (смешанная модель).

Формулировка результата: «разница учебников с поправкой на входной уровень учеников и школы»,
не причинный эффект. Интервалы строятся по t-распределению с df = min(школ учебника,
школ эталона) − 1, чтобы не занижать неопределённость при малом числе школ.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from .config import Config
from .data_io import Dataset
from .panel import build_panel

warnings.filterwarnings("ignore")
TB = "C(textbook_id, Treatment('{ref}'))"


def bh_fdr(p: list[float]) -> list[float]:
    p = np.asarray(p, float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1)
    return out.tolist()


def _status(n_schools: int, cfg: Config) -> tuple[str, str]:
    if n_schools < cfg.min_schools_per_textbook:
        return "insufficient", "Недостаточно данных для утверждения"
    if n_schools < cfg.reliable_schools_per_textbook:
        return "tentative", "Ориентировочно: мало школ, интервал вероятно занижен"
    return "ok", "Достаточно школ"


def _covariates(panel: pd.DataFrame) -> list[str]:
    terms = []
    if "prior_z" in panel:
        terms += ["prior_z", "school_prior_z"]
    for c in ("instruction_language", "locality_type", "teacher_experience_band"):
        if c in panel and panel[c].nunique() > 1:
            terms.append(f"C({c})")
    return terms


def _gee_check(panel: pd.DataFrame, ref: str, others: list[str], cov: list[str], cfg: Config, tbs) -> dict:
    """Проверка устойчивости: биномиальная logit-модель (GEE, кластеры = школы, поправка Манкла–ДеРуэна
    для малого числа кластеров). Результат — средний маргинальный эффект в п.п. с симуляционным интервалом."""
    import statsmodels.api as sm
    d = panel.dropna(subset=[c for c in ("prior_z",) if c in panel]).reset_index(drop=True)
    tb_term = TB.format(ref=ref)
    f = "pct ~ " + " + ".join([tb_term, "C(topic)"] + cov)
    try:
        m = smf.gee(f, groups="school_id", data=d, family=sm.families.Binomial()).fit(cov_type="bias_reduced")
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    rng = np.random.default_rng(cfg.seed)
    V = np.asarray(m.cov_params())
    beta = np.asarray(m.params)
    draws = rng.multivariate_normal(beta, V, size=300)
    names = list(m.params.index)
    out = {}
    sub = d.sample(min(len(d), 6000), random_state=cfg.seed)
    for tb in others:
        d0, d1 = sub.copy(), sub.copy()
        d0["textbook_id"], d1["textbook_id"] = ref, tb
        di = m.model.data.model_spec.design_info if hasattr(m.model.data, "model_spec") else m.model.data.design_info
        import patsy
        X0 = np.asarray(patsy.build_design_matrices([di], d0)[0])
        X1 = np.asarray(patsy.build_design_matrices([di], d1)[0])
        sig = lambda z: 1 / (1 + np.exp(-z))  # noqa: E731
        ame = np.array([(sig(X1 @ b) - sig(X0 @ b)).mean() * 100 for b in draws])
        est = float((sig(X1 @ beta) - sig(X0 @ beta)).mean() * 100)
        df = max(1, min(tbs[tb], tbs[ref]) - 1)
        tcrit = stats.t.ppf(1 - (1 - cfg.confidence_level) / 2, df)
        se = float(ame.std(ddof=1))
        out[tb] = dict(estimate=est, ci=[est - tcrit * se, est + tcrit * se], se=se)
    return out


def analyze_textbooks(ds: Dataset, cfg: Config) -> dict:
    if ds.teaching is None:
        return dict(available=False, reason="Нет файла teaching (учебник по классу).")
    panel = build_panel(ds).dropna(subset=["textbook_id"])
    tbs = panel.groupby("textbook_id").school_id.nunique().sort_values(ascending=False)
    if len(tbs) < 2:
        return dict(available=False, reason="Нужно минимум два учебника для сравнения.")
    ref = tbs.index[0]
    others = [t for t in tbs.index if t != ref]
    naive = panel.groupby("textbook_id").pct.mean() * 100

    cov = _covariates(panel)
    adjusted = "prior_z" in panel
    warnings_ = []
    if not adjusted:
        warnings_.append("Нет входного уровня учеников: поправка невозможна, разницы считать нельзя.")
    tb_term = TB.format(ref=ref)
    base = " + ".join([tb_term, "C(topic)"] + cov)
    m = smf.mixedlm(f"pct ~ {base}", panel.dropna(subset=[c for c in ("prior_z",) if c in panel]),
                    groups=panel.dropna(subset=[c for c in ("prior_z",) if c in panel])["school_id"]).fit(reml=True)
    z = stats.norm.ppf(1 - (1 - cfg.confidence_level) / 2)
    res = []
    for tb in others:
        key = f"{tb_term}[T.{tb}]"
        b, se = m.params[key] * 100, m.bse[key] * 100
        df = max(1, min(tbs[tb], tbs[ref]) - 1)
        tcrit = stats.t.ppf(1 - (1 - cfg.confidence_level) / 2, df)
        st, msg = _status(int(min(tbs[tb], tbs[ref])), cfg)
        res.append(dict(textbook=tb, vs=ref, estimate=float(b), ci=[float(b - tcrit * se), float(b + tcrit * se)],
                        ci_normal=[float(b - z * se), float(b + z * se)], df=int(df), se=float(se),
                        schools=int(tbs[tb]), schools_ref=int(tbs[ref]), status=st, status_text=msg,
                        naive_diff=float(naive[tb] - naive[ref]),
                        significant=bool(st != "insufficient" and (b - tcrit * se > 0 or b + tcrit * se < 0))))
    gee = _gee_check(panel, ref, others, cov, cfg, tbs) if adjusted else {}
    for r in res:
        g = gee.get(r["textbook"])
        if g:
            r["robust"] = g
            r["robust_agrees"] = bool((g["estimate"] > 0) == (r["estimate"] > 0) and
                                      g["ci"][0] <= r["ci"][1] and r["ci"][0] <= g["ci"][1])
    table = [dict(textbook=t, schools=int(tbs[t]), students=int(panel[panel.textbook_id == t].student_pseudo_id.nunique()),
                  naive_mean=float(naive[t])) for t in tbs.index]

    simpson = None
    if "school_type" in panel:
        sim = panel.groupby(["school_type", "textbook_id"]).pct.mean().mul(100).unstack()
        cnt = panel.groupby(["school_type", "textbook_id"]).school_id.nunique().unstack(fill_value=0)
        simpson = dict(columns=list(sim.columns), rows=[
            dict(school_type=st, means=[None if pd.isna(v) else float(v) for v in sim.loc[st]],
                 schools=[int(cnt.loc[st, c]) for c in sim.columns]) for st in sim.index])

    # взаимодействие учебник × тема
    inter = f"pct ~ {tb_term} * C(topic)" + ("" if not cov else " + " + " + ".join(cov))
    mi = smf.mixedlm(inter, panel.dropna(subset=[c for c in ("prior_z",) if c in panel]),
                     groups=panel.dropna(subset=[c for c in ("prior_z",) if c in panel])["school_id"]).fit(reml=True)
    topics = sorted(panel.topic.unique())
    names = list(mi.params.index)
    cov_p = mi.cov_params()
    rows, pvals = [], []
    for tb in others:
        main = f"{tb_term}[T.{tb}]"
        for t in topics:
            k = f"{tb_term}[T.{tb}]:C(topic)[T.{t}]"
            L = pd.Series(0.0, index=names)
            L[main] = 1.0
            if k in names:
                L[k] = 1.0
            est = float(L @ mi.params)
            var = float(L.values @ cov_p.loc[names, names].values @ L.values)
            se = np.sqrt(max(var, 1e-12))
            p = 2 * (1 - stats.norm.cdf(abs(est / se)))
            rows.append(dict(textbook=tb, topic=t, estimate=est * 100, se=se * 100, p=float(p)))
            pvals.append(p)
    for r, q in zip(rows, bh_fdr(pvals)):
        r["q_fdr"] = float(q)
        r["significant_fdr"] = bool(q < cfg.fdr_alpha)
        r["ci"] = [r["estimate"] - z * r["se"], r["estimate"] + z * r["se"]]
    rows.sort(key=lambda r: -abs(r["estimate"]))

    return dict(
        available=True, reference=ref, adjusted=adjusted, table=table, comparisons=res, simpson=simpson,
        topic_effects=rows, warnings=warnings_,
        covariates=[c for c in cov],
        method=(f"Смешанная линейная модель: доля верных ~ учебник + тема + входной уровень ученика + средний "
                f"входной уровень школы (Mundlak) + язык + тип местности + стаж учителя; случайный эффект школы. "
                f"Эталон — учебник {ref}. Интервалы: t-распределение, df = min(число школ) − 1. "
                f"Проверка устойчивости: биномиальная logit-модель (GEE, поправка Манкла–ДеРуэна для малого числа школ). "
                f"По темам: поправка Бенджамини–Хохберга (FDR)."),
        caveat=("Это разница с поправкой на наблюдаемые характеристики, а не причинный эффект учебника: "
                "ненаблюдаемые различия школ могут оставаться. Сравнение возможно только межшкольное."),
    )
