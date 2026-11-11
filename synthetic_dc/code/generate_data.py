#!/usr/bin/env python3
"""Генератор синтетических данных для проекта Data-Driven Curriculum.

Моделируется один предмет (алгебра, 7 класс) и один учебный год.
Результаты заданий генерируются по 2PL IRT-модели, а «истина» (сложность тем,
эффект учебников, эффект школ и часов) записывается отдельно в ground_truth.json.
Файлы данных ground_truth не содержат: аналитический код не должен его видеть.

Заложенные сценарии (все параметры видны в блоке ПАРАМЕТРЫ ИСТИНЫ ниже):
  1. Парадокс Симпсона: учебник A стоит в основном в сильных школах (лицеи, НИШ),
     поэтому наивное сравнение средних ставит его первым, хотя его истинный
     эффект отрицательный.
  2. У учебника A дополнительная слабость на теме «Функции и графики»,
     у учебника C дополнительная сила на теме «Системы линейных уравнений».
  3. Сложность тем разная; часы на тему влияют на результат с убывающей отдачей,
     причём сильнее на трудных темах.

Все данные синтетические. Реальных людей, школ и результатов здесь нет.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# ПАРАМЕТРЫ ИСТИНЫ
# ---------------------------------------------------------------------------
TOPICS = [
    # (код, название, истинная сложность b в логитах, базовые часы, коэффициент отдачи часов)
    ("T01", "Числовые и буквенные выражения", -0.8, 5, 0.12),
    ("T02", "Степень с натуральным показателем", -0.4, 5, 0.12),
    ("T03", "Одночлены", -0.3, 4, 0.12),
    ("T04", "Многочлены", 0.0, 6, 0.15),
    ("T05", "Формулы сокращённого умножения", 0.5, 8, 0.30),
    ("T06", "Разложение на множители", 0.7, 8, 0.30),
    ("T07", "Линейные уравнения", -0.5, 6, 0.12),
    ("T08", "Функции и графики", 0.5, 8, 0.30),
    ("T09", "Системы линейных уравнений", 0.8, 8, 0.30),
    ("T10", "Текстовые задачи", 0.9, 7, 0.30),
    ("T11", "Алгебраические дроби", 0.6, 7, 0.30),
    ("T12", "Статистика и вероятность", -0.2, 4, 0.12),
]

# Общий эффект учебника (логиты) относительно B. Отрицательный у A: A хуже.
TEXTBOOK_BASE = {"A": -0.30, "B": 0.00, "C": 0.10}
# Дополнительные эффекты на отдельных темах.
TEXTBOOK_TOPIC_EXTRA = {("A", "T08"): -0.35, ("C", "T09"): 0.25}

# Смещение способностей по типу школы.
SCHOOL_TYPES = {
    #            число,  сдвиг способностей, доли учебников A / B / C
    "elite": dict(n=12, mu=0.90, p=(0.85, 0.05, 0.10)),
    "urban": dict(n=24, mu=0.00, p=(0.25, 0.40, 0.35)),
    "rural": dict(n=24, mu=-0.60, p=(0.05, 0.75, 0.20)),
}
TEACHER_EFFECT = {"<3": -0.10, "3-10": 0.00, ">10": 0.10}

TASKS_PER_TOPIC = (6, 8)
CLASSES_PER_SCHOOL = 2
CLASS_SIZE = (22, 30)
ABSENT_RATE = 0.03
YEAR = "2026/27"
QUARTER_OF_TOPIC = {t[0]: 1 + i // 3 for i, t in enumerate(TOPICS)}
_MONTHS = [10, 11, 12, 1, 2, 3, 3, 4, 4, 5, 5, 5]
DATE_OF_TOPIC = {t[0]: f"{2026 if m >= 9 else 2027}-{m:02d}-15" for t, m in zip(TOPICS, _MONTHS)}


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def build_schools(rng):
    rows = []
    sid = 0
    for stype, cfg in SCHOOL_TYPES.items():
        for _ in range(cfg["n"]):
            sid += 1
            lang_p_kz = 0.35 if stype == "elite" else (0.45 if stype == "urban" else 0.75)
            rows.append(dict(
                school_id=f"S{sid:03d}",
                school_type=stype,
                locality_type="village" if stype == "rural" else "city",
                instruction_language="kz" if rng.random() < lang_p_kz else "ru",
                textbook_id=rng.choice(["A", "B", "C"], p=cfg["p"]),
                school_effect=cfg["mu"] + rng.normal(0, 0.25),
            ))
    schools = pd.DataFrame(rows)
    # гарантируем, что у каждого учебника не меньше 8 школ (иначе оценки шумные)
    for tb in "ABC":
        while (schools.textbook_id == tb).sum() < 8:
            idx = rng.choice(schools.index[schools.textbook_id != tb])
            schools.loc[idx, "textbook_id"] = tb
    return schools


def build_items(rng):
    rows = []
    for code, name, b_topic, _, _ in TOPICS:
        n_tasks = rng.integers(TASKS_PER_TOPIC[0], TASKS_PER_TOPIC[1] + 1)
        for k in range(1, n_tasks + 1):
            rows.append(dict(
                assessment_id=f"AS-{code}",
                topic_id=code,
                section_or_topic=name,
                task_id=f"{code}-{k:02d}",
                descriptor_id=f"D-{code}-{k:02d}",
                max_score=1,
                assessment_type="summative",
                quarter=QUARTER_OF_TOPIC[code],
                date=DATE_OF_TOPIC[code],
                true_b=b_topic + rng.normal(0, 0.5),
                true_a=float(np.clip(rng.lognormal(0, 0.25), 0.6, 1.8)),
            ))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", type=str, required=True, help="папка для файлов данных")
    ap.add_argument("--hours-follow-difficulty", type=float, default=0.0,
                    help="сила связи плановых часов со сложностью темы (0 = случайные часы, как в базовом наборе). "
                         "Моделирует реальность: трудным темам дают больше часов (обратная причинность).")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    schools = build_schools(rng)
    items = build_items(rng)
    topic_meta = {t[0]: t for t in TOPICS}

    # --- классы, учителя, часы ------------------------------------------------
    class_rows, hours_rows = [], []
    for _, s in schools.iterrows():
        for c in range(CLASSES_PER_SCHOOL):
            label = f"7{'АБ'[c]}"
            band = rng.choice(["<3", "3-10", ">10"], p=[0.25, 0.45, 0.30])
            class_rows.append(dict(
                school_id=s.school_id, **{"class": label}, grade=7, subject="algebra",
                textbook_id=s.textbook_id, teacher_experience_band=band,
                class_effect=rng.normal(0, 0.15)))
            for code, _, _, base_h, _ in TOPICS:
                noise = rng.uniform(0.75, 1.25)
                b_topic = topic_meta[code][2]
                tilt = 1.0 + args.hours_follow_difficulty * float(np.clip(b_topic, -1, 1))
                planned = int(np.clip(round(base_h * noise * tilt), 2, 14))
                hours_rows.append(dict(school_id=s.school_id, **{"class": label},
                                       topic_id=code, planned_hours=planned))
    classes = pd.DataFrame(class_rows)
    hours = pd.DataFrame(hours_rows)

    # --- ученики --------------------------------------------------------------
    stud_rows = []
    n = 0
    for _, cl in classes.iterrows():
        s = schools.loc[schools.school_id == cl.school_id].iloc[0]
        size = rng.integers(CLASS_SIZE[0], CLASS_SIZE[1] + 1)
        for _ in range(size):
            n += 1
            base = s.school_effect + rng.normal(0, 0.9)           # способность до учебного года
            prior = int(np.clip(round(50 + 15 * (base + rng.normal(0, 0.4))), 0, 100))
            stud_rows.append(dict(
                student_pseudo_id=f"P{n:06d}", school_id=cl.school_id, **{"class": cl["class"]},
                grade=7, prior_score=prior, true_base=base,
                theta=base + cl.class_effect + TEACHER_EFFECT[cl.teacher_experience_band]))
    students = pd.DataFrame(stud_rows)

    # --- результаты -----------------------------------------------------------
    hours_idx = hours.set_index(["school_id", "class", "topic_id"]).planned_hours
    cls_idx = classes.set_index(["school_id", "class"]).textbook_id
    result_chunks = []
    for (sid, label), grp in students.groupby(["school_id", "class"]):
        tb = cls_idx[(sid, label)]
        for code, _, _, base_h, gamma in TOPICS:
            it = items[items.topic_id == code]
            eff = TEXTBOOK_BASE[tb] + TEXTBOOK_TOPIC_EXTRA.get((tb, code), 0.0)
            eff += gamma * np.log(hours_idx[(sid, label, code)] / base_h)
            present = rng.random(len(grp)) > ABSENT_RATE
            g = grp[present]
            if g.empty:
                continue
            logit = it.true_a.values[None, :] * (
                g.theta.values[:, None] + eff - it.true_b.values[None, :])
            score = (rng.random(logit.shape) < sigmoid(logit)).astype(int)
            df = pd.DataFrame(score, columns=it.task_id.values)
            df.insert(0, "student_pseudo_id", g.student_pseudo_id.values)
            result_chunks.append(df.melt(id_vars="student_pseudo_id",
                                         var_name="task_id", value_name="score"))
    results = pd.concat(result_chunks, ignore_index=True)

    # --- запись файлов в схеме из отчёта ---------------------------------------
    items_pub = items.drop(columns=["true_b", "true_a"])
    items_pub.to_csv(out / "items.csv", index=False)
    schools[["school_id", "school_type", "locality_type", "instruction_language"]].to_csv(
        out / "schools.csv", index=False)
    students[["student_pseudo_id", "school_id", "class", "grade", "prior_score"]].to_csv(
        out / "students.csv", index=False)
    classes[["school_id", "class", "grade", "subject", "textbook_id",
             "teacher_experience_band"]].to_csv(out / "teaching.csv", index=False)
    hours.to_csv(out / "hours.csv", index=False)
    results.to_csv(out / "results.csv", index=False)

    long = (results
            .merge(students[["student_pseudo_id", "school_id", "class"]], on="student_pseudo_id")
            .merge(items_pub, on="task_id"))
    long["academic_year"] = YEAR
    long["subject"] = "algebra"
    long = long[["school_id", "class", "academic_year", "quarter", "subject",
                 "student_pseudo_id", "assessment_type", "assessment_id",
                 "section_or_topic", "task_id", "descriptor_id", "score", "max_score", "date"]]
    long.to_csv(out / "results_long.csv", index=False)

    truth = dict(
        seed=args.seed,
        note="Истина для проверки моделей. Аналитический код не должен читать этот файл.",
        topic_difficulty={t[0]: t[2] for t in TOPICS},
        task_difficulty=dict(zip(items.task_id, items.true_b.round(4))),
        task_discrimination=dict(zip(items.task_id, items.true_a.round(4))),
        textbook_base=TEXTBOOK_BASE,
        textbook_topic_extra={f"{k[0]}:{k[1]}": v for k, v in TEXTBOOK_TOPIC_EXTRA.items()},
        school_type_shift={k: v["mu"] for k, v in SCHOOL_TYPES.items()},
        hours_gamma={t[0]: t[4] for t in TOPICS},
        base_hours={t[0]: t[3] for t in TOPICS},
        teacher_effect=TEACHER_EFFECT,
        school_effect=dict(zip(schools.school_id, schools.school_effect.round(4))),
    )
    (out / "ground_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print(f"schools={len(schools)} classes={len(classes)} students={len(students)} "
          f"items={len(items)} result_rows={len(results)}")
    print(schools.groupby(["school_type", "textbook_id"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main()
