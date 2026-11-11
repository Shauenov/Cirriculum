#!/usr/bin/env python3
"""Проверка на синтетике: наивное сравнение учебников против модели с поправкой.

Часть 1 (методист видит это): использует только файлы данных, без истины.
Часть 2 (валидация): читает ground_truth.json и сравнивает оценки с истиной.

Запуск:  python3 -I analyze.py --data ../data --out ../report.md
"""
import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def load(data):
    d = Path(data)
    res = pd.read_csv(d / "results.csv")
    items = pd.read_csv(d / "items.csv")[["task_id", "topic_id", "section_or_topic"]]
    stud = pd.read_csv(d / "students.csv")
    sch = pd.read_csv(d / "schools.csv")
    teach = pd.read_csv(d / "teaching.csv")
    return res, items, stud, sch, teach


def build_panel(res, items, stud, sch, teach):
    """Одна строка = ученик × тема, значение = доля верных заданий."""
    r = res.merge(items, on="task_id")
    p = (r.groupby(["student_pseudo_id", "topic_id"]).score.mean().rename("pct").reset_index())
    p = (p.merge(stud, on="student_pseudo_id")
          .merge(sch, on="school_id")
          .merge(teach[["school_id", "class", "textbook_id", "teacher_experience_band"]],
                 on=["school_id", "class"]))
    p["prior_z"] = (p.prior_score - p.prior_score.mean()) / p.prior_score.std()
    # средний входной уровень школы: контекстный эффект (подход Mundlak)
    p["school_prior"] = p.groupby("school_id").prior_score.transform("mean")
    p["school_prior_z"] = (p.school_prior - p.school_prior.mean()) / p.school_prior.std()
    return p


def fmt(x, d=1):
    return f"{x:.{d}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    res, items, stud, sch, teach = load(args.data)
    panel = build_panel(res, items, stud, sch, teach)
    lines = []
    add = lines.append

    # ---------------- Часть 1а. Наивное сравнение --------------------------
    add("# Проверка на синтетических данных\n")
    add("## 1. Наивное сравнение: средний балл по учебнику\n")
    naive = panel.groupby("textbook_id").pct.mean().mul(100)
    n_sch = panel.groupby("textbook_id").school_id.nunique()
    add("| Учебник | Школ | Средний балл, % |\n|---|---|---|")
    for tb in naive.index:
        add(f"| {tb} | {n_sch[tb]} | {fmt(naive[tb])} |")
    add(f"\nНаивный вывод: лучший учебник — **{naive.idxmax()}** "
        f"(на {fmt(naive.max() - naive['B'])} п.п. выше B).\n")

    # ---------------- Часть 1б. Парадокс Симпсона ---------------------------
    add("## 2. Тот же показатель внутри типов школ (парадокс Симпсона)\n")
    sim = panel.groupby(["school_type", "textbook_id"]).pct.mean().mul(100).unstack()
    cnt = panel.groupby(["school_type", "textbook_id"]).school_id.nunique().unstack(fill_value=0)
    add("| Тип школы | A | B | C | школ A / B / C |\n|---|---|---|---|---|")
    for st in ["elite", "urban", "rural"]:
        add(f"| {st} | {fmt(sim.loc[st, 'A'])} | {fmt(sim.loc[st, 'B'])} | {fmt(sim.loc[st, 'C'])} "
            f"| {cnt.loc[st, 'A']} / {cnt.loc[st, 'B']} / {cnt.loc[st, 'C']} |")
    flips = [(st, sim.loc[st, "A"] - sim.loc[st, "B"]) for st in ["elite", "urban", "rural"]]
    add("\nРазница A − B внутри типа школы: " +
        ", ".join(f"{st}: {d:+.1f} п.п." for st, d in flips) + ".\n")

    # ---------------- Часть 1в. Иерархическая модель ------------------------
    add("## 3. Модель с поправкой: случайный эффект школы + входной уровень\n")
    base = ("pct ~ C(textbook_id, Treatment('B')) + C(topic_id) + prior_z + school_prior_z"
            " + C(instruction_language) + C(locality_type) + C(teacher_experience_band)")
    m = smf.mixedlm(base, panel, groups=panel["school_id"]).fit(reml=True)
    est = {}
    add("| Учебник против B | Оценка, п.п. | 95% интервал, п.п. |\n|---|---|---|")
    for tb in ["A", "C"]:
        key = f"C(textbook_id, Treatment('B'))[T.{tb}]"
        b, se = m.params[key] * 100, m.bse[key] * 100
        est[tb] = (b, b - 1.96 * se, b + 1.96 * se)
        add(f"| {tb} | {b:+.1f} | [{est[tb][1]:+.1f}; {est[tb][2]:+.1f}] |")
    add("\nИнтервалы учитывают только кластеризацию по школам; число школ на учебник — "
        f"A: {n_sch['A']}, B: {n_sch['B']}, C: {n_sch['C']}.\n")

    # ---------------- Часть 1г. Эффект учебника по темам --------------------
    add("## 4. Разница учебников по темам (взаимодействие учебник × тема)\n")
    inter = ("pct ~ C(textbook_id, Treatment('B')) * C(topic_id) + prior_z + school_prior_z"
             " + C(instruction_language) + C(locality_type) + C(teacher_experience_band)")
    mi = smf.mixedlm(inter, panel, groups=panel["school_id"]).fit(reml=True)
    topic_ids = sorted(panel.topic_id.unique())
    topic_name = dict(zip(items.topic_id, items.section_or_topic))
    rows = []
    for tb in ["A", "C"]:
        main = mi.params[f"C(textbook_id, Treatment('B'))[T.{tb}]"]
        for t in topic_ids:
            k = f"C(textbook_id, Treatment('B'))[T.{tb}]:C(topic_id)[T.{t}]"
            eff = main + (mi.params[k] if k in mi.params else 0.0)
            rows.append((tb, t, eff * 100))
    tt = pd.DataFrame(rows, columns=["tb", "topic", "eff"])
    add("Самые заметные отклонения (в п.п. относительно учебника B):\n")
    add("| Учебник | Тема | Оценка, п.п. |\n|---|---|---|")
    for _, r in tt.reindex(tt.eff.abs().sort_values(ascending=False).index).head(6).iterrows():
        add(f"| {r.tb} | {r.topic} {topic_name[r.topic]} | {r.eff:+.1f} |")
    add("")

    # ---------------- Часть 1д. Сложность тем -------------------------------
    diff_idx = (1 - panel.groupby("topic_id").pct.mean()).rename("difficulty_index")
    add("## 5. Сложность тем (1 − средняя доля верных)\n")
    add("| Тема | Индекс сложности |\n|---|---|")
    for t, v in diff_idx.sort_values(ascending=False).items():
        add(f"| {t} {topic_name[t]} | {v:.2f} |")
    add("")

    # ---------------- Часть 2. Валидация по истине --------------------------
    truth = json.loads((Path(args.data) / "ground_truth.json").read_text(encoding="utf-8"))
    add("## 6. Валидация: сравнение с заложенной истиной\n")
    a = truth["task_discrimination"]
    b = truth["task_difficulty"]
    tasks_by_topic = items.groupby("topic_id").task_id.apply(list).to_dict()
    grid = np.random.default_rng(0).normal(0, 1.0, 4000)   # эталонная популяция N(0,1)

    def true_pct(tb):
        vals = []
        for t, tasks in tasks_by_topic.items():
            extra = truth["textbook_base"][tb] + truth["textbook_topic_extra"].get(f"{tb}:{t}", 0.0)
            p = np.mean([sigmoid(a[k] * (grid + extra - b[k])).mean() for k in tasks])
            vals.append(p)
        return np.mean(vals) * 100

    tp = {tb: true_pct(tb) for tb in "ABC"}
    add("Истинный эффект учебника в п.п. относительно B (эталонная популяция N(0,1), "
        "средний часовой режим):\n")
    add("| Учебник | Истина | Наивная оценка | Оценка модели | Интервал модели | Попал? |\n|---|---|---|---|---|---|")
    ok = {}
    for tb in ["A", "C"]:
        truth_eff = tp[tb] - tp["B"]
        naive_eff = naive[tb] - naive["B"]
        lo, hi = est[tb][1], est[tb][2]
        ok[tb] = lo <= truth_eff <= hi
        add(f"| {tb} | {truth_eff:+.1f} | {naive_eff:+.1f} | {est[tb][0]:+.1f} "
            f"| [{lo:+.1f}; {hi:+.1f}] | {'да' if ok[tb] else 'нет'} |")
    add("")

    # заложенные темы-исключения
    def tb_topic(tb, t):
        k = f"C(textbook_id, Treatment('B'))[T.{tb}]:C(topic_id)[T.{t}]"
        return (mi.params[f"C(textbook_id, Treatment('B'))[T.{tb}]"] + mi.params.get(k, 0.0)) * 100

    def true_topic_pp(tb, t):
        tasks = tasks_by_topic[t]
        f = lambda tbk: np.mean([sigmoid(a[k] * (grid + truth["textbook_base"][tbk]
                                 + truth["textbook_topic_extra"].get(f"{tbk}:{t}", 0.0) - b[k])).mean()
                                 for k in tasks]) * 100
        return f(tb) - f("B")

    add("Заложенные исключения по темам (учебник A на T08, учебник C на T09):\n")
    add("| Случай | Истина, п.п. | Оценка модели, п.п. |\n|---|---|---|")
    for tb, t in [("A", "T08"), ("C", "T09")]:
        add(f"| {tb} на {t} | {true_topic_pp(tb, t):+.1f} | {tb_topic(tb, t):+.1f} |")
    add("")

    true_b_topic = pd.Series(truth["topic_difficulty"])
    rho = spearmanr(diff_idx.reindex(true_b_topic.index), true_b_topic).statistic
    add(f"Ранговая корреляция индекса сложности с истинной сложностью тем: **ρ = {rho:.2f}**.\n")

    naive_correct = naive.idxmax() == "C"  # истинный лучший: C (+0.10)
    add("## Итог\n")
    add(f"- Наивное сравнение называет лучшим **{naive.idxmax()}**; по истине лучший — **C**, "
        f"а A хуже B. Наивный ответ {'верный' if naive_correct else 'неверный'}.")
    add(f"- Модель с поправкой: интервалы накрывают истину для A: {'да' if ok['A'] else 'нет'}, "
        f"для C: {'да' if ok['C'] else 'нет'}.")
    add(f"- Сложность тем восстановлена с ρ = {rho:.2f}.")
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
