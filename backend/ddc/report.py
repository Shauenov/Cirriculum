"""Записка для методсовета: DOCX и PDF, RU/KZ.

Числа считает аналитика. Текст — шаблон; при наличии OPENROUTER_API_KEY LLM только
переписывает краткое резюме по JSON с агрегатами (персональных данных там нет).
Казахская версия — черновик, требует проверки носителем языка.
"""
from __future__ import annotations

import io
import json
import os
import urllib.request
from pathlib import Path

L = {
    "ru": dict(
        title="Аналитическая записка для методсовета", synth="СИНТЕТИЧЕСКИЕ ДАННЫЕ. Реальных школ и учеников нет.",
        summary="Резюме", hard="Сложные для усвоения темы", tb="Сравнение учебников", hours="Сценарий распределения часов",
        limits="Ограничения", topic="Тема", diff="Индекс сложности", ci="Интервал", est="Оценка с поправкой, п.п.",
        naive="Наивная разница, п.п.", schools="Школ", status="Статус", cur="Сейчас", rec="Рекомендуется", rng="Диапазон",
        insufficient="Недостаточно данных для утверждения", gain="Ожидаемый прирост средней доли верных, п.п.",
        draft="", vs="против",
        tb_intro="Разница учебников с поправкой на входной уровень учеников и школы (не причинный эффект), с интервалом.",
    ),
    "kz": dict(
        title="Әдістемелік кеңеске арналған талдамалық жазба", synth="СИНТЕТИКАЛЫҚ ДЕРЕКТЕР. Нақты мектептер мен оқушылар жоқ.",
        summary="Қорытынды", hard="Меңгеруге қиын тақырыптар", tb="Оқулықтарды салыстыру", hours="Сағаттарды бөлу сценарийі",
        limits="Шектеулер", topic="Тақырып", diff="Күрделілік индексі", ci="Аралық", est="Түзетілген бағалау, п.т.",
        naive="Қарапайым айырма, п.т.", schools="Мектеп", status="Мәртебе", cur="Қазір", rec="Ұсынылады", rng="Диапазон",
        insufficient="Растау үшін деректер жеткіліксіз", gain="Дұрыс жауаптың орташа үлесінің күтілетін өсімі, п.т.",
        draft="Қазақша нұсқа — жоба, ана тілі тасымалдаушысы тексеруі қажет.", vs="қарсы",
        tb_intro="Оқушылар мен мектептің бастапқы деңгейіне түзетілген оқулықтар айырмасы (себептік әсер емес), аралықпен.",
    ),
}


def _summary_template(res: dict, lang: str) -> str:
    d = res["difficulty"]["topics"][:3]
    names = ", ".join(t["topic"] for t in d)
    tb = res["textbooks"]
    parts = []
    if lang == "ru":
        parts.append(f"Наиболее сложные темы: {names}.")
        if tb.get("available"):
            for c in tb["comparisons"]:
                if c["status"] == "insufficient":
                    parts.append(f"Учебник {c['textbook']}: недостаточно данных для утверждения.")
                else:
                    parts.append(f"Учебник {c['textbook']} против {c['vs']}: {c['estimate']:+.1f} п.п. "
                                 f"[{c['ci'][0]:+.1f}; {c['ci'][1]:+.1f}] с поправкой на уровень учеников и школы "
                                 f"(наивная разница {c['naive_diff']:+.1f} п.п.).")
        h = res["hours"]
        if h.get("available"):
            parts.append(f"Сценарий часов при неизменной сумме {h['total']} ч: ожидаемый прирост "
                         f"{h['gain_pp']:+.2f} п.п. [{h['gain_ci'][0]:+.2f}; {h['gain_ci'][1]:+.2f}]; "
                         "если интервал включает 0, выигрыш не доказан.")
    else:
        parts.append(f"Ең күрделі тақырыптар: {names}.")
        if tb.get("available"):
            for c in tb["comparisons"]:
                if c["status"] == "insufficient":
                    parts.append(f"{c['textbook']} оқулығы: растау үшін деректер жеткіліксіз.")
                else:
                    parts.append(f"{c['textbook']} оқулығы {c['vs']} оқулығына қарсы: {c['estimate']:+.1f} п.т. "
                                 f"[{c['ci'][0]:+.1f}; {c['ci'][1]:+.1f}] (қарапайым айырма {c['naive_diff']:+.1f} п.т.).")
        h = res["hours"]
        if h.get("available"):
            parts.append(f"Сағат сценарийі (жалпы {h['total']} сағат өзгермейді): күтілетін өсім {h['gain_pp']:+.2f} п.т. "
                         f"[{h['gain_ci'][0]:+.2f}; {h['gain_ci'][1]:+.2f}].")
    return " ".join(parts)


def llm_summary(res: dict, lang: str, template: str) -> tuple[str, str]:
    """Возвращает (текст, источник). Без ключа или при сбое — шаблон."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return template, "template"
    payload = dict(
        top_topics=res["difficulty"]["topics"][:5],
        textbooks=[{k: c[k] for k in ("textbook", "vs", "estimate", "ci", "schools", "status", "naive_diff")}
                   for c in res["textbooks"].get("comparisons", [])],
        hours=dict(total=res["hours"].get("total"), gain_pp=res["hours"].get("gain_pp"), gain_ci=res["hours"].get("gain_ci")),
    )
    prompt = ("Перепиши резюме для методсовета на языке: " + ("русском" if lang == "ru" else "казахском") +
              ". Используй ТОЛЬКО числа из JSON, ничего не вычисляй и не добавляй. Не используй причинные слова "
              "(«причиняет», «доказано»); пиши «разница с поправкой на уровень учеников и школы», всегда с интервалом; "
              "при статусе insufficient пиши «Недостаточно данных для утверждения». Не обещай «разрешённых» перераспределений часов. "
              "2–5 предложений.\nJSON:\n" + json.dumps(payload, ensure_ascii=False) + "\nЧерновик:\n" + template)
    body = json.dumps(dict(model=os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5"),
                           messages=[{"role": "user", "content": prompt}], max_tokens=600)).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            txt = json.loads(r.read())["choices"][0]["message"]["content"].strip()
        return (txt, "llm") if txt else (template, "template")
    except Exception:  # noqa: BLE001
        return template, "template"


def build_blocks(res: dict, lang: str = "ru", use_llm: bool = True) -> dict:
    t = L[lang]
    tpl = _summary_template(res, lang)
    summary, src = llm_summary(res, lang, tpl) if use_llm else (tpl, "template")
    tops = [[x["topic"], f"{x['difficulty']:.2f}", f"[{x['ci'][0]:.2f}; {x['ci'][1]:.2f}]"] for x in res["difficulty"]["topics"][:6]]
    tb_rows = []
    tb = res["textbooks"]
    if tb.get("available"):
        for c in tb["comparisons"]:
            tb_rows.append([f"{c['textbook']} {t['vs']} {c['vs']}",
                            t["insufficient"] if c["status"] == "insufficient" else f"{c['estimate']:+.1f} [{c['ci'][0]:+.1f}; {c['ci'][1]:+.1f}]",
                            f"{c['naive_diff']:+.1f}", f"{c['schools']}/{c['schools_ref']}", c["status_text"] if lang == "ru" else c["status"]])
    h_rows = []
    h = res["hours"]
    if h.get("available"):
        for r in h["rows"]:
            h_rows.append([r["topic"], str(r["current"]), str(r["recommended"]), f"{r['range'][0]}–{r['range'][1]}"])
    limits = list(h.get("assumptions", [])) + ([tb["caveat"]] if tb.get("available") else [])
    return dict(t=t, summary=summary, summary_source=src, tops=tops, tb_rows=tb_rows, h_rows=h_rows, limits=limits,
                synthetic=res.get("synthetic", False), hours_text=h.get("recommendation_text", ""),
                gain=(f"{t['gain']}: {h['gain_pp']:+.2f} [{h['gain_ci'][0]:+.2f}; {h['gain_ci'][1]:+.2f}]" if h.get("available") else ""))


def to_docx(res: dict, lang: str = "ru", use_llm: bool = True) -> bytes:
    from docx import Document
    b = build_blocks(res, lang, use_llm)
    t = b["t"]
    doc = Document()
    doc.add_heading(t["title"], 0)
    if b["synthetic"]:
        doc.add_paragraph(t["synth"]).runs[0].bold = True
    if t["draft"]:
        doc.add_paragraph(t["draft"])
    doc.add_heading(t["summary"], 1)
    doc.add_paragraph(b["summary"])

    def table(head, rows):
        if not rows:
            return
        tb = doc.add_table(rows=1, cols=len(head))
        tb.style = "Light Grid Accent 1"
        for i, hd in enumerate(head):
            tb.rows[0].cells[i].text = hd
        for r in rows:
            cells = tb.add_row().cells
            for i, v in enumerate(r):
                cells[i].text = str(v)
    doc.add_heading(t["hard"], 1)
    table([t["topic"], t["diff"], t["ci"]], b["tops"])
    doc.add_heading(t["tb"], 1)
    doc.add_paragraph(t["tb_intro"])
    table(["", t["est"], t["naive"], t["schools"], t["status"]], b["tb_rows"])
    doc.add_heading(t["hours"], 1)
    doc.add_paragraph(b["hours_text"])
    table([t["topic"], t["cur"], t["rec"], t["rng"]], b["h_rows"])
    if b["gain"]:
        doc.add_paragraph(b["gain"])
    doc.add_heading(t["limits"], 1)
    for s in b["limits"]:
        doc.add_paragraph(s, style="List Bullet")
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


def _font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for p in (r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(p).exists():
            pdfmetrics.registerFont(TTFont("DDC", p))
            bold = p.replace("arial.ttf", "arialbd.ttf").replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
            pdfmetrics.registerFont(TTFont("DDC-B", bold if Path(bold).exists() else p))
            return "DDC", "DDC-B"
    return "Helvetica", "Helvetica-Bold"


def to_pdf(res: dict, lang: str = "ru", use_llm: bool = True) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    f, fb = _font()
    b = build_blocks(res, lang, use_llm)
    t = b["t"]
    body = ParagraphStyle("b", fontName=f, fontSize=10, leading=14)
    h1 = ParagraphStyle("h", fontName=fb, fontSize=13, leading=17, spaceBefore=10, spaceAfter=4)
    cell = ParagraphStyle("c", fontName=f, fontSize=8.5, leading=11)
    bio = io.BytesIO()
    doc = SimpleDocTemplate(bio, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    el = [Paragraph(t["title"], ParagraphStyle("t", fontName=fb, fontSize=17, leading=22, spaceAfter=6))]
    if b["synthetic"]:
        el.append(Paragraph(f"<b>{t['synth']}</b>", body))
    if t["draft"]:
        el.append(Paragraph(t["draft"], body))

    def tbl(head, rows, widths=None):
        if not rows:
            return
        data = [[Paragraph(f"<b>{x}</b>", cell) for x in head]] + [[Paragraph(str(x), cell) for x in r] for r in rows]
        tt = Table(data, colWidths=widths, repeatRows=1)
        tt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7"))]))
        el.extend([tt, Spacer(1, 6)])
    el += [Paragraph(t["summary"], h1), Paragraph(b["summary"], body), Paragraph(t["hard"], h1)]
    tbl([t["topic"], t["diff"], t["ci"]], b["tops"])
    el += [Paragraph(t["tb"], h1), Paragraph(t["tb_intro"], body), Spacer(1, 4)]
    tbl(["", t["est"], t["naive"], t["schools"], t["status"]], b["tb_rows"])
    el += [Paragraph(t["hours"], h1), Paragraph(b["hours_text"], body), Spacer(1, 4)]
    tbl([t["topic"], t["cur"], t["rec"], t["rng"]], b["h_rows"])
    if b["gain"]:
        el.append(Paragraph(b["gain"], body))
    el.append(Paragraph(t["limits"], h1))
    for s in b["limits"]:
        el.append(Paragraph("• " + s, body))
    doc.build(el)
    return bio.getvalue()
