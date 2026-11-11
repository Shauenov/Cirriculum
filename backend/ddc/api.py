"""FastAPI: /import, /analyze/difficulty, /analyze/textbooks, /optimize/hours, /report."""
from __future__ import annotations

import threading
import uuid
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import Config
from .data_io import ImportError_, build_dataset
from .dif import analyze_dif
from .difficulty import analyze_difficulty
from .explain import why_hours, why_textbook
from .hours import analyze_hours, scenario
from .pipeline import load_demo
from .report import to_docx, to_pdf
from .textbooks import analyze_textbooks

app = FastAPI(title="Data-Driven Curriculum")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
STORE: dict[str, dict] = {}
LOCK = threading.Lock()


class Params(BaseModel):
    min_factor: Optional[float] = None
    max_factor: Optional[float] = None


class Plan(BaseModel):
    plan: dict[str, int]


def _get(did: str) -> dict:
    if did not in STORE:
        raise HTTPException(404, "Набор данных не найден: загрузите файлы заново.")
    return STORE[did]


def _cfg(entry, **kw) -> Config:
    return Config(**{**entry["cfg"].to_dict(), **{k: v for k, v in kw.items() if v is not None}})


def _register(ds) -> dict:
    did = uuid.uuid4().hex[:10]
    STORE[did] = dict(ds=ds, cfg=Config(), cache={})
    return dict(id=did, quality=ds.quality.to_dict(), synthetic=ds.synthetic)


def _csv(*lines):
    return "\n".join(lines) + "\n"


TEMPLATES = {
    "results_long.csv": _csv(
        "school_id,class,student_pseudo_id,task_id,section_or_topic,score,max_score,assessment_id,assessment_type,date",
        "S001,7A,P000001,T01-01,Тема 1,1,1,AS-T01,summative,2026-10-15",
        "S001,7A,P000002,T01-01,Тема 1,0,1,AS-T01,summative,2026-10-15"),
    "students.csv": _csv("student_pseudo_id,school_id,class,grade,prior_score", "P000001,S001,7A,7,57", "P000002,S001,7A,7,62"),
    "schools.csv": _csv("school_id,school_type,locality_type,instruction_language", "S001,urban,city,ru"),
    "teaching.csv": _csv("school_id,class,grade,subject,textbook_id,teacher_experience_band", "S001,7A,7,algebra,A,3-10"),
    "hours.csv": _csv("school_id,class,section_or_topic,planned_hours", "S001,7A,Тема 1,6"),
    "README.txt": _csv(
        "student_pseudo_id - случайный токен (не ИИН, не ФИО). Таблица соответствий остаётся в школе.",
        "score/max_score - балл и максимум за задание; единица данных: ученик x работа x задание.",
        "prior_score - входной уровень ученика (0-100). Без students и teaching сравнение учебников отключается."),
}


@app.get("/templates")
def templates():
    import io
    import zipfile
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        for k, v in TEMPLATES.items():
            z.writestr(k, "﻿" + v if k.endswith(".csv") else v)
    return Response(bio.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="templates.zip"'})


@app.get("/validation")
def validation():
    """Результаты проверки на синтетике с известной истиной (генерируются тестами/скриптами)."""
    import json
    from pathlib import Path
    base = Path(__file__).resolve().parents[1]
    out = {}
    for key, fn in (("textbooks", "validation_textbooks.json"), ("hours", "validation_hours.json")):
        f = base / fn
        out[key] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    return out


EDITABLE = {"confidence_level": (0.8, 0.99), "min_schools_per_textbook": (2, 60), "reliable_schools_per_textbook": (5, 100),
            "hours_min_factor": (0.3, 1.0), "hours_max_factor": (1.0, 3.0), "hours_max_step": (1, 6), "bootstrap_reps": (20, 500),
            "bad_item_discrimination": (0.0, 0.5), "fdr_alpha": (0.01, 0.2)}


@app.get("/config")
def get_config(id: str):
    return dict(config=_get(id)["cfg"].to_dict(), editable={k: list(v) for k, v in EDITABLE.items()})


@app.post("/config")
def set_config(id: str, body: dict):
    e = _get(id)
    upd = {}
    for k, v in body.items():
        if k not in EDITABLE:
            raise HTTPException(400, f"Параметр «{k}» нельзя менять.")
        lo, hi = EDITABLE[k]
        if not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise HTTPException(400, f"{k}: допустимо от {lo} до {hi}.")
        upd[k] = type(getattr(e["cfg"], k))(v) if getattr(e["cfg"], k) is not None else int(v)
    with LOCK:
        e["cfg"] = Config(**{**e["cfg"].to_dict(), **upd})
        e["cache"].clear()
    return dict(config=e["cfg"].to_dict())


@app.get("/health")
def health():
    return dict(ok=True, warm=sorted(PRE))


@app.post("/import")
async def import_files(files: list[UploadFile] = File(...)):
    raw = {f.filename: await f.read() for f in files}
    try:
        ds = build_dataset(raw, synthetic=False)
    except ImportError_ as e:
        raise HTTPException(422, str(e))
    return _register(ds)


PRE: dict[str, dict] = {}     # прогретые демо-наборы: имя -> запись с готовым кешем
DEMO_SUB = {"main": "", "small": "small"}


@app.post("/demo/{name}")
def demo(name: str):
    if name not in DEMO_SUB:
        raise HTTPException(404, "Доступны наборы: main, small")
    if name in PRE:      # быстрый путь: анализ уже посчитан при старте сервера
        src = PRE[name]
        did = uuid.uuid4().hex[:10]
        STORE[did] = dict(ds=src["ds"], cfg=Config(), cache=dict(src["cache"]))
        return dict(id=did, quality=src["ds"].quality.to_dict(), synthetic=True)
    return _register(load_demo(DEMO_SUB[name]))


def _difficulty(e):
    if "difficulty" not in e["cache"]:
        e["cache"]["difficulty"] = analyze_difficulty(e["ds"], e["cfg"])
    return e["cache"]["difficulty"]


def _textbooks(e):
    if "textbooks" not in e["cache"]:
        e["cache"]["textbooks"] = analyze_textbooks(e["ds"], e["cfg"])
    return e["cache"]["textbooks"]


def _hours(e, min_factor=None, max_factor=None):
    key = ("hours", min_factor, max_factor)
    if key not in e["cache"]:
        cfg = _cfg(e, hours_min_factor=min_factor, hours_max_factor=max_factor)
        r = analyze_hours(e["ds"], cfg, _difficulty(e))
        e["cache"][key] = (r.pop("_draws", None), r, cfg)
    return e["cache"][key]


@app.get("/analyze/difficulty")
def difficulty(id: str):
    with LOCK:
        return _difficulty(_get(id))


@app.get("/analyze/dif")
def dif(id: str):
    with LOCK:
        e = _get(id)
        if "dif" not in e["cache"]:
            e["cache"]["dif"] = analyze_dif(e["ds"], e["cfg"])
        return e["cache"]["dif"]


@app.get("/analyze/textbooks")
def textbooks(id: str):
    with LOCK:
        return _textbooks(_get(id))


@app.post("/optimize/hours")
def hours(id: str, p: Params = Params()):
    with LOCK:
        return _hours(_get(id), p.min_factor, p.max_factor)[1]


@app.post("/optimize/scenario")
def hours_scenario(id: str, body: Plan, min_factor: Optional[float] = None, max_factor: Optional[float] = None):
    with LOCK:
        d, r, cfg = _hours(_get(id), min_factor, max_factor)
    if d is None:
        raise HTTPException(422, r.get("reason", "Часы недоступны"))
    return scenario(d, body.plan, cfg)


def _bundle(e) -> dict:
    _, h, _ = _hours(e)
    return dict(quality=e["ds"].quality.to_dict(), synthetic=e["ds"].synthetic, config=e["cfg"].to_dict(),
                difficulty=_difficulty(e), textbooks=_textbooks(e), hours=h)


@app.get("/why/hours")
def why_h(id: str, topic: str):
    with LOCK:
        return why_hours(_bundle(_get(id)), topic)


@app.get("/why/textbook")
def why_t(id: str, textbook: str):
    with LOCK:
        return why_textbook(_bundle(_get(id)), textbook)


@app.get("/report")
def report(id: str, lang: str = "ru", fmt: str = "docx", llm: bool = True):
    if lang not in ("ru", "kz") or fmt not in ("docx", "pdf"):
        raise HTTPException(400, "lang: ru|kz, fmt: docx|pdf")
    with LOCK:
        res = _bundle(_get(id))
    data = to_docx(res, lang, llm) if fmt == "docx" else to_pdf(res, lang, llm)
    mt = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document" if fmt == "docx"
          else "application/pdf")
    return Response(data, media_type=mt, headers={"Content-Disposition": f'attachment; filename="note_{lang}.{fmt}"'})


def _warm():
    for name in ("small", "main"):
        try:
            e = dict(ds=load_demo(DEMO_SUB[name]), cfg=Config(), cache={})
            _difficulty(e)
            _textbooks(e)
            _hours(e)
            e["cache"]["dif"] = analyze_dif(e["ds"], e["cfg"])
            PRE[name] = e
        except Exception:  # noqa: BLE001
            pass


@app.on_event("startup")
def _startup():
    threading.Thread(target=_warm, daemon=True).start()
