import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from ddc.api import app


@pytest.fixture(scope="module")
def client_id():
    c = TestClient(app)
    return c, c.post("/demo/small").json()["id"]


def test_templates_zip():
    z = zipfile.ZipFile(io.BytesIO(TestClient(app).get("/templates").content))
    assert "results_long.csv" in z.namelist()
    assert z.read("results_long.csv").decode("utf-8-sig").startswith("school_id,class")


def test_import_rejects_pii_via_api():
    bad = b"school_id,class,student_fio,task_id,section_or_topic,score,max_score\nS1,7A,X,T1,A,1,1\n"
    r = TestClient(app).post("/import", files=[("files", ("results_long.csv", bad, "text/csv"))])
    assert r.status_code == 422 and "персональные" in r.json()["detail"]


def test_unknown_dataset_404():
    assert TestClient(app).get("/analyze/difficulty", params={"id": "nope"}).status_code == 404


def test_endpoints_and_reports(client_id):
    c, i = client_id
    assert c.get("/analyze/textbooks", params={"id": i}).json()["available"]
    h = c.post("/optimize/hours", params={"id": i}, json={}).json()
    assert all(abs(r["delta"]) <= 1 for r in h["rows"])            # консервативный сценарий: шаг ≤ 1 ч
    plan = {r["topic"]: r["recommended"] for r in h["rows"]}
    ok = c.post("/optimize/scenario", params={"id": i}, json={"plan": plan}).json()
    assert "gain_pp" in ok
    plan[next(iter(plan))] += 1
    assert "error" in c.post("/optimize/scenario", params={"id": i}, json={"plan": plan}).json()   # сумма изменена
    assert "headline" in c.get("/why/hours", params={"id": i, "topic": h["rows"][0]["topic"]}).json()
    for fmt in ("docx", "pdf"):
        for lang in ("ru", "kz"):
            r = c.get("/report", params={"id": i, "lang": lang, "fmt": fmt, "llm": "false"})
            assert r.status_code == 200 and len(r.content) > 5000
    assert c.get("/report", params={"id": i, "lang": "en"}).status_code == 400


def test_config_edit_validates_and_invalidates_cache(client_id):
    c, i = client_id
    assert c.post("/config", params={"id": i}, json={"confidence_level": 5}).status_code == 400
    assert c.post("/config", params={"id": i}, json={"seed": 1}).status_code == 400
    r = c.post("/config", params={"id": i}, json={"min_schools_per_textbook": 4})
    assert r.status_code == 200 and r.json()["config"]["min_schools_per_textbook"] == 4
    tb = c.get("/analyze/textbooks", params={"id": i}).json()
    assert all(x["status"] != "insufficient" for x in tb["comparisons"])    # порог снижен — метка исчезла
    c.post("/config", params={"id": i}, json={"min_schools_per_textbook": 8})


def test_hours_bad_bounds_400(client_id):
    c, i = client_id
    assert c.post("/optimize/hours", params={"id": i}, json={"min_factor": 2.0, "max_factor": 1.0}).status_code == 400


def test_small_demo_topic_effects_gated(client_id):
    c, i = client_id
    tb = c.get("/analyze/textbooks", params={"id": i}).json()
    ins = {x["textbook"] for x in tb["comparisons"] if x["status"] == "insufficient"}
    assert all(not e["significant_dev"] for e in tb["topic_effects"] if e["textbook"] in ins)
