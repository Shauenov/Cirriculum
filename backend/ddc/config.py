"""Параметры анализа. Пороги — допущения проекта, а не нормативы."""
from dataclasses import dataclass, asdict


@dataclass
class Config:
    confidence_level: float = 0.95
    # Число школ на учебник: ниже min — «Недостаточно данных»;
    # между min и reliable — оценка ориентировочная (интервалы вероятно занижены,
    # по Maas & Hox, 2005 ориентир ~50 групп).
    min_schools_per_textbook: int = 8
    reliable_schools_per_textbook: int = 30
    min_students_per_topic: int = 30
    # Задание считается «плохим», если дискриминативность ниже порога (ориентир Gradescope)
    bad_item_discrimination: float = 0.20
    bad_item_p_low: float = 0.03
    bad_item_p_high: float = 0.97
    # Оптимизатор часов: границы относительно текущего плана (допущение, не норма)
    hours_min_factor: float = 0.6
    hours_max_factor: float = 1.5
    hours_abs_min: int = 2
    hours_pool: bool = True             # полное сжатие отдачи к линии «сложность → отдача»
    hours_max_step: int | None = 1      # максимум изменения часов по теме относительно плана
    bootstrap_reps: int = 200
    seed: int = 2026
    fdr_alpha: float = 0.05

    def to_dict(self):
        return asdict(self)
