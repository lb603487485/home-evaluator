"""S9 feedback capture: POST /api/feedback appends self-contained JSONL lines.
Capture-only — nothing here feeds the engine."""

import json
import os

os.environ["AGENT_NO_LLM"] = "1"

import httpx
import pytest

from app.main import app

PAYLOAD = {
    "session_id": "abc123",
    "rating": 4,
    "comment": "range looked tight",
    "user_estimate": 700_000,
    "snapshot": {
        "subject": {"community": "Evanston", "sqft": 1850},
        "estimate": 712_000, "low": 690_000, "high": 730_000, "confidence": "B",
        "comps": [{"address_key": "100 A ST NW", "score": 90.0}],
        "flags": ["DATA_CONFLICT"],
    },
}


@pytest.fixture
async def client(tmp_path, monkeypatch):
    from app import api
    monkeypatch.setattr(api, "FEEDBACK_PATH", tmp_path / "feedback.jsonl")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, tmp_path / "feedback.jsonl"


async def test_feedback_appends_self_contained_line(client):
    c, path = client
    r = await c.post("/api/feedback", json=PAYLOAD)
    assert r.status_code == 200
    assert r.json() == {"stored": True}
    [line] = path.read_text().splitlines()
    rec = json.loads(line)
    assert rec["session_id"] == "abc123" and rec["rating"] == 4
    assert rec["user_estimate"] == 700_000
    # the line must be interpretable with no session store: snapshot rides along
    assert rec["snapshot"]["estimate"] == 712_000
    assert rec["snapshot"]["confidence"] == "B"
    assert rec["snapshot"]["comps"][0]["address_key"] == "100 A ST NW"
    assert rec["at"]  # server-side timestamp


async def test_feedback_appends_not_overwrites(client):
    c, path = client
    await c.post("/api/feedback", json=PAYLOAD)
    await c.post("/api/feedback", json={**PAYLOAD, "rating": 2})
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["rating"] == 2


async def test_feedback_rating_bounds(client):
    c, path = client
    for bad in (0, 6):
        r = await c.post("/api/feedback", json={**PAYLOAD, "rating": bad})
        assert r.status_code == 422
    assert not path.exists()  # rejected feedback writes nothing


async def test_feedback_minimal_payload(client):
    c, path = client
    r = await c.post("/api/feedback", json={
        "session_id": "x", "rating": 5, "snapshot": {"estimate": 1}})
    assert r.status_code == 200
    rec = json.loads(path.read_text())
    assert rec["comment"] == "" and rec["user_estimate"] is None
