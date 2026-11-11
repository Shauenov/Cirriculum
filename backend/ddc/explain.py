"""Объяснимость: «Почему?» для каждой рекомендации."""


def why_hours(results: dict, topic: str) -> dict:
    h = results["hours"]
    row = next((r for r in h.get("rows", []) if r["topic"] == topic), None)
    if row is None:
        return dict(error="Тема не найдена")
    q = results["quality"]["stats"]
    diff = next((t for t in results["difficulty"]["topics"] if t["topic"] == topic), None)
    direction = "увеличить" if row["delta"] > 0 else "уменьшить" if row["delta"] < 0 else "оставить"
    lo, hi = row["range"]
    robust = lo <= row["recommended"] <= hi
    return dict(
        topic=topic,
        headline=f"{direction.capitalize()} часы по теме: {row['current']} → {row['recommended']} (диапазон по бутстрепу {lo}–{hi})",
        data=f"{q.get('schools')} школ, {q.get('students')} учеников; плановые часы по классам; сложность темы "
             f"{diff['difficulty']:.2f}" + (f" [{diff['ci'][0]:.2f}; {diff['ci'][1]:.2f}]" if diff else ""),
        method=h["method"],
        evidence=(f"Калиброванная отдача: {row['beta']:.3f} (доли верных на единицу ln часов; сырая оценка "
                  f"{row['beta_raw']:.3f}, SE {row['beta_se']:.3f})." if row["beta_raw"] is not None else
                  "Для темы недостаточно вариации часов, использована средняя отдача."),
        uncertainty=("Рекомендованное значение внутри бутстреп-диапазона: изменение устойчиво не доказано."
                     if robust else "Рекомендация выходит за бутстреп-диапазон."),
        limits=h["assumptions"],
        scope=h["recommendation_text"],
    )


def why_textbook(results: dict, textbook: str) -> dict:
    tb = results["textbooks"]
    if not tb.get("available"):
        return dict(error=tb.get("reason"))
    c = next((x for x in tb["comparisons"] if x["textbook"] == textbook), None)
    if c is None:
        return dict(error="Учебник не найден")
    return dict(
        textbook=textbook,
        headline=(f"Разница {textbook} против {c['vs']} с поправкой на уровень учеников и школы: "
                  f"{c['estimate']:+.1f} п.п. [{c['ci'][0]:+.1f}; {c['ci'][1]:+.1f}]"
                  if c["status"] != "insufficient" else "Недостаточно данных для утверждения"),
        data=f"школ: {c['schools']} против {c['schools_ref']} (эталон)",
        method=tb["method"], uncertainty=c["status_text"],
        evidence=f"Наивная разница без поправки: {c['naive_diff']:+.1f} п.п.",
        limits=[tb["caveat"]],
    )
