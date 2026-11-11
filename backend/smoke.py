from fastapi.testclient import TestClient

from ddc.api import app

c = TestClient(app)
r = c.post("/demo/small").json()
print("schools", r["quality"]["stats"]["schools"])
i = r["id"]
tb = c.get("/analyze/textbooks", params={"id": i}).json()
print([(x["textbook"], round(x["estimate"], 1), x["status"]) for x in tb["comparisons"]])
h = c.post("/optimize/hours", params={"id": i}, json={}).json()
print(h["gain_pp"], h["gain_ci"])
plan = {x["topic"]: x["recommended"] for x in h["rows"]}
print(c.post("/optimize/scenario", params={"id": i}, json={"plan": plan}).json())
for f in ("docx", "pdf"):
    for l in ("ru", "kz"):
        x = c.get("/report", params={"id": i, "lang": l, "fmt": f})
        print(f, l, x.status_code, len(x.content))
print(c.get("/why/hours", params={"id": i, "topic": h["rows"][0]["topic"]}).json()["headline"])
