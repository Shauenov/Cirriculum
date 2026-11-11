"""Сборка панели «ученик × тема» из импортированного набора данных."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data_io import Dataset


def build_panel(ds: Dataset, exclude_tasks=None) -> pd.DataFrame:
    r = ds.results
    if exclude_tasks:
        r = r[~r.task_id.isin(exclude_tasks)]
    g = r.groupby(["student_pseudo_id", "school_id", "class", "section_or_topic"], as_index=False).agg(
        got=("score", "sum"), mx=("max_score", "sum"))
    g["pct"] = g.got / g.mx
    p = g.rename(columns={"section_or_topic": "topic"})
    if ds.students is not None:
        p = p.merge(ds.students[["student_pseudo_id", "prior_score"]].drop_duplicates("student_pseudo_id"),
                    on="student_pseudo_id", how="left")
        sd = p.prior_score.std()
        p["prior_z"] = (p.prior_score - p.prior_score.mean()) / (sd if sd > 0 else 1)
        # средний входной уровень школы: контекстный эффект (подход Mundlak)
        sp = p.groupby("school_id").prior_score.transform("mean")
        sps = sp.std()
        p["school_prior_z"] = (sp - sp.mean()) / (sps if sps and sps > 0 else 1)
    if ds.schools is not None:
        keep = [c for c in ("school_id", "school_type", "locality_type", "instruction_language")
                if c in ds.schools.columns]
        p = p.merge(ds.schools[keep], on="school_id", how="left")
    if ds.teaching is not None:
        keep = [c for c in ("school_id", "class", "textbook_id", "teacher_experience_band")
                if c in ds.teaching.columns]
        p = p.merge(ds.teaching[keep].drop_duplicates(["school_id", "class"]),
                    on=["school_id", "class"], how="left")
    if ds.hours is not None:
        h = ds.hours.rename(columns={"section_or_topic": "topic"})[["school_id", "class", "topic", "planned_hours"]]
        p = p.merge(h.drop_duplicates(["school_id", "class", "topic"]),
                    on=["school_id", "class", "topic"], how="left")
    return p
