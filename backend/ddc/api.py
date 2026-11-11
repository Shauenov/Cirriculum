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


@app.get("/health")
def health():
    return dict(ok=True)


@app.post("/import")
async def import_files(files: list[UploadFile] = File(...)):
    raw = {f.filename: await f.read() for f in files}
    try:
        ds = build_dataset(raw, synthetic=False)
    except ImportError_ as e:
        raise HTTPException(422, str(e))
    return _register(ds)


@app.post("/demo/{name}")
def demo(name: str):
    sub = {"main": "", "small": "small"}.get(name)
    if sub is None:
        raise HTTPException(404, "Доступны наборы: main, small")
    return _register(load_demo(sub))


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
