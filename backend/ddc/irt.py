"""2PL IRT, маргинальный максимум правдоподобия (EM, квадратура Гаусса–Эрмита).

Все ученики решают общий набор заданий, поэтому шкала способности общая: сложность задания b
не зависит от того, какие школы и ученики его решали (в отличие от доли верных).
Для работ, которые решают разные группы, нужны якорные задания (общие для работ), иначе шкалы
разных работ несопоставимы. Здесь якорение обеспечивается тем, что ученики общие.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _sig(x):
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def fit_2pl(Y: np.ndarray, n_iter: int = 40, q: int = 31, init=None, a_prior_sd: float = 0.5):
    """Y: N×J, значения в [0,1], NaN = нет ответа. Возвращает a, b (по заданиям)."""
    N, J = Y.shape
    mask = ~np.isnan(Y)
    Yf = np.where(mask, Y, 0.0)
    theta = np.linspace(-4, 4, q)
    prior = np.exp(-0.5 * theta ** 2)
    prior /= prior.sum()
    if init is None:
        p = np.clip(np.nanmean(Y, axis=0), 0.02, 0.98)
        a = np.ones(J)
        b = -np.log(p / (1 - p))
    else:
        a, b = init[0].copy(), init[1].copy()
    for _ in range(n_iter):
        P = _sig(a[None, :, None] * (theta[None, None, :] - b[None, :, None]))   # 1×J×Q
        P = np.clip(P, 1e-9, 1 - 1e-9)
        lp, lq = np.log(P), np.log(1 - P)
        # логправдоподобие по ученику и узлу
        ll = np.einsum("nj,jq->nq", Yf, lp[0]) + np.einsum("nj,jq->nq", mask * (1 - Yf), lq[0])
        ll += np.log(prior)[None, :]
        ll -= ll.max(axis=1, keepdims=True)
        w = np.exp(ll)
        w /= w.sum(axis=1, keepdims=True)                                         # N×Q
        r = (Yf.T @ w)                                                            # J×Q
        n = (mask.T.astype(float) @ w)
        # M-шаг: Ньютон по (a, c), c = −a·b, с мягким приором на log a
        c = -a * b
        for _ in range(3):
            z = a[:, None] * theta[None, :] + c[:, None]
            p = _sig(z)
            resid = r - n * p
            g_a = (resid * theta[None, :]).sum(1) - (np.log(a) / a_prior_sd ** 2) / a
            g_c = resid.sum(1)
            W = n * p * (1 - p)
            h_aa = -(W * theta[None, :] ** 2).sum(1) - 1.0 / (a_prior_sd ** 2 * a ** 2)
            h_ac = -(W * theta[None, :]).sum(1)
            h_cc = -W.sum(1)
            det = h_aa * h_cc - h_ac ** 2
            det = np.where(np.abs(det) < 1e-9, -1e-9, det)
            da = (h_cc * g_a - h_ac * g_c) / det
            dc = (-h_ac * g_a + h_aa * g_c) / det
            a = np.clip(a - np.clip(da, -0.5, 0.5), 0.3, 3.0)
            c = c - np.clip(dc, -0.8, 0.8)
        b = -c / a
    return a, b


def topic_irt(ds, bad_tasks=()):
    """Возвращает (a, b по заданиям как DataFrame, матрица ответов)."""
    r = ds.results
    M = r.pivot_table(index="student_pseudo_id", columns="task_id", values="score_frac", aggfunc="first")
    a, b = fit_2pl(M.values)
    items = pd.DataFrame(dict(task_id=M.columns, a=a, b=b))
    topic_of = r.drop_duplicates("task_id").set_index("section_or_topic" if False else "task_id").section_or_topic
    items["topic"] = items.task_id.map(topic_of)
    return items, M
