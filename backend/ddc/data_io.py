"""Импорт и валидация данных.

Обязательный файл: results_long (CSV/XLSX), единица данных — ученик × работа × задание
× балл / максимум. Необязательные контекстные файлы: students (входной уровень),
schools, teaching (учебник, стаж), hours (плановые часы по темам), items.
Реальные ФИО и ИИН платформа не принимает.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import pandas as pd

REQUIRED_RESULTS = ["school_id", "class", "student_pseudo_id", "task_id",
                    "section_or_topic", "score", "max_score"]
OPTIONAL_RESULTS = ["academic_year", "quarter", "subject", "assessment_type",
                    "assessment_id", "descriptor_id", "date"]
FORBIDDEN_COLUMNS = re.compile(r"(^|_)(fio|iin|inn|фио|иин|surname|lastname|firstname|"
                               r"full_?name|фамилия|имя|отчество|birth|dob)($|_)", re.I)
IIN_LIKE = re.compile(r"^\d{12}$")
ROLES = ("results", "students", "schools", "teaching", "hours", "items")


class ImportError_(Exception):
    """Блокирующая ошибка импорта (понятное сообщение пользователю)."""


@dataclass
class QualityReport:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def ok(self):
        return not self.errors

    def to_dict(self):
        return dict(ok=self.ok, errors=self.errors, warnings=self.warnings, stats=self.stats)


@dataclass
class Dataset:
    results: pd.DataFrame
    students: pd.DataFrame | None = None
    schools: pd.DataFrame | None = None
    teaching: pd.DataFrame | None = None
    hours: pd.DataFrame | None = None
    items: pd.DataFrame | None = None
    quality: QualityReport = field(default_factory=QualityReport)
    synthetic: bool = False


def read_table(name: str, content: bytes) -> pd.DataFrame:
    lower = name.lower()
    try:
        if lower.endswith((".xlsx", ".xls")):
            return pd.read_excel(io.BytesIO(content))
        for enc in ("utf-8-sig", "cp1251"):
            try:
                return pd.read_csv(io.BytesIO(content), encoding=enc, sep=None, engine="python")
            except UnicodeDecodeError:
                continue
        raise ImportError_(f"Файл «{name}»: не удалось определить кодировку (нужен UTF-8 или Windows-1251).")
    except ImportError_:
        raise
    except Exception as e:  # noqa: BLE001
        raise ImportError_(f"Файл «{name}» не читается как CSV/Excel: {e}") from e


def guess_role(name: str, df: pd.DataFrame) -> str | None:
    n = name.lower()
    for role in ("results", "students", "schools", "teaching", "hours", "items"):
        if role in n:
            return role
    cols = set(df.columns)
    if {"task_id", "score", "student_pseudo_id"} <= cols:
        return "results"
    if "prior_score" in cols:
        return "students"
    if "textbook_id" in cols:
        return "teaching"
    if "planned_hours" in cols:
        return "hours"
    if "school_type" in cols or "instruction_language" in cols:
        return "schools"
    if "max_score" in cols and "task_id" in cols:
        return "items"
    return None


def _privacy_check(df: pd.DataFrame, name: str, rep: QualityReport):
    bad = [c for c in df.columns if FORBIDDEN_COLUMNS.search(str(c))]
    if bad:
        rep.errors.append(f"Файл «{name}»: колонки {bad} похожи на персональные данные (ФИО, ИИН, дата рождения). "
                          "Платформа не принимает такие поля: замените идентификатор на случайный токен "
                          "(таблица соответствий остаётся в школе).")
    for c in ("student_pseudo_id",):
        if c in df.columns:
            s = df[c].astype(str).head(2000)
            if s.str.match(IIN_LIKE).mean() > 0.5:
                rep.errors.append(f"Файл «{name}»: значения в «{c}» похожи на ИИН (12 цифр). Используйте случайный токен.")


def build_dataset(files: dict[str, bytes], synthetic: bool = False) -> Dataset:
    """files: имя файла -> содержимое. Роль файла определяется по имени/колонкам."""
    rep = QualityReport()
    tables: dict[str, pd.DataFrame] = {}
    for name, content in files.items():
        df = read_table(name, content)
        df.columns = [str(c).strip() for c in df.columns]
        role = guess_role(name, df)
        if role is None:
            rep.warnings.append(f"Файл «{name}»: роль не определена, пропущен.")
            continue
        _privacy_check(df, name, rep)
        tables[role] = df
    if rep.errors:
        raise ImportError_("\n".join(rep.errors))
    if "results" not in tables:
        raise ImportError_("Не найден файл с результатами (results_long.csv): нужны колонки "
                           + ", ".join(REQUIRED_RESULTS) + ".")
    res = _validate_results(tables["results"], rep)
    ds = Dataset(results=res, students=tables.get("students"), schools=tables.get("schools"),
                 teaching=tables.get("teaching"), hours=tables.get("hours"),
                 items=tables.get("items"), quality=rep, synthetic=synthetic)
    _validate_context(ds, rep)
    if rep.errors:
        raise ImportError_("\n".join(rep.errors))
    return ds


def _validate_results(df: pd.DataFrame, rep: QualityReport) -> pd.DataFrame:
    missing = [c for c in REQUIRED_RESULTS if c not in df.columns]
    if missing:
        raise ImportError_(f"В файле результатов нет обязательных колонок: {missing}. "
                           f"Найдены: {list(df.columns)}.")
    df = df.copy()
    n0 = len(df)
    for c in ("score", "max_score"):
        conv = pd.to_numeric(df[c], errors="coerce")
        bad = conv.isna() & df[c].notna()
        if bad.any():
            rep.errors.append(f"Колонка «{c}»: {int(bad.sum())} нечисловых значений (пример строки {int(bad.idxmax()) + 2}).")
        df[c] = conv
    nulls = df[REQUIRED_RESULTS].isna().sum()
    for c, k in nulls.items():
        if k:
            rep.warnings.append(f"Пропуски в «{c}»: {int(k)} строк исключены из анализа.")
    df = df.dropna(subset=REQUIRED_RESULTS)
    if (df.max_score <= 0).any():
        rep.errors.append("max_score должен быть положительным.")
    over = df.score > df.max_score
    neg = df.score < 0
    if over.any() or neg.any():
        rep.errors.append(f"Баллы вне диапазона [0; max_score]: {int((over | neg).sum())} строк.")
    dup = df.duplicated(["student_pseudo_id", "task_id"], keep="first")
    if dup.any():
        rep.warnings.append(f"Дубликаты «ученик × задание»: {int(dup.sum())} строк удалены (оставлена первая).")
        df = df[~dup]
    df["score_frac"] = df.score / df.max_score
    df["student_pseudo_id"] = df.student_pseudo_id.astype(str)
    df["school_id"] = df.school_id.astype(str)
    df["class"] = df["class"].astype(str)
    rep.stats.update(rows_in=int(n0), rows_used=int(len(df)),
                     schools=int(df.school_id.nunique()),
                     students=int(df.student_pseudo_id.nunique()),
                     tasks=int(df.task_id.nunique()), topics=int(df.section_or_topic.nunique()))
    if df.school_id.nunique() < 3:
        rep.errors.append("Меньше 3 школ: межшкольный анализ невозможен.")
    # доля заданий на ученика
    per_student = df.groupby("student_pseudo_id").task_id.nunique()
    thin = (per_student < 0.5 * df.task_id.nunique()).sum()
    if thin:
        rep.warnings.append(f"{int(thin)} учеников выполнили меньше половины заданий — их данные неполны.")
    return df.reset_index(drop=True)


def _validate_context(ds: Dataset, rep: QualityReport):
    known_students = set(ds.results.student_pseudo_id)
    if ds.students is None:
        rep.warnings.append("Нет файла students (входной уровень, prior_score): сравнение учебников без поправки на "
                            "входной уровень ненадёжно и будет отключено.")
    else:
        for c in ("student_pseudo_id", "prior_score"):
            if c not in ds.students.columns:
                rep.errors.append(f"students: нет колонки «{c}».")
        if not rep.errors:
            ds.students["student_pseudo_id"] = ds.students.student_pseudo_id.astype(str)
            ds.students["prior_score"] = pd.to_numeric(ds.students.prior_score, errors="coerce")
            cover = ds.students.student_pseudo_id.isin(known_students).mean()
            if cover < 0.9:
                rep.warnings.append(f"students: только {cover:.0%} учеников из students есть в результатах.")
            miss = known_students - set(ds.students.student_pseudo_id)
            if miss:
                rep.warnings.append(f"students: для {len(miss)} учеников из результатов нет входного уровня.")
    if ds.teaching is None:
        rep.warnings.append("Нет файла teaching (учебник по классу): модуль сравнения учебников недоступен.")
    elif "textbook_id" not in ds.teaching.columns or not {"school_id", "class"} <= set(ds.teaching.columns):
        rep.errors.append("teaching: нужны колонки school_id, class, textbook_id.")
    else:
        for c in ("school_id", "class"):
            ds.teaching[c] = ds.teaching[c].astype(str)
    if ds.schools is not None:
        ds.schools["school_id"] = ds.schools.school_id.astype(str)
    if ds.hours is None:
        rep.warnings.append("Нет файла hours (плановые часы по темам): рекомендации по часам недоступны.")
    else:
        ds.hours["school_id"] = ds.hours.school_id.astype(str)
        ds.hours["class"] = ds.hours["class"].astype(str)
        if "section_or_topic" not in ds.hours.columns:
            if "topic_id" in ds.hours.columns and ds.items is not None and "topic_id" in ds.items.columns:
                m = ds.items[["topic_id", "section_or_topic"]].drop_duplicates()
                ds.hours = ds.hours.merge(m, on="topic_id", how="left")
            else:
                rep.errors.append("hours: нужна колонка section_or_topic (или topic_id вместе с файлом items).")
    rep.stats["context"] = {k: (getattr(ds, k) is not None) for k in ("students", "schools", "teaching", "hours", "items")}
