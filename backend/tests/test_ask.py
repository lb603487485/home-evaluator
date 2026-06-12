import json
import os

os.environ["AGENT_NO_LLM"] = "1"

import httpx
import pytest

from app.main import app

CONTEXT = {
    "subject": dict(community="Evanston", address="", property_type="detached",
                    beds=3, baths=2.5, sqft=1850, year_built=2020, lot_sqft=4000,
                    garage_stalls=2, notes=""),
    "valuation": {"estimate": 712000},
}


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class _Fake:
    def __init__(self, payload: dict):
        self._payload = payload

    async def ainvoke(self, _messages):
        class M:
            content = json.dumps(self._payload)
        return M()


async def test_ask_no_llm_degrades_to_200(client):
    r = await client.post("/api/ask", json={"question": "why A?", "context": CONTEXT})
    assert r.status_code == 200
    assert r.json()["type"] == "answer"


async def test_ask_answer_passthrough(client, monkeypatch):
    from agent import llm
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model",
                        lambda *a, **k: _Fake({"type": "answer", "text": "B because spread"}))
    r = await client.post("/api/ask", json={"question": "why B?", "context": CONTEXT})
    assert r.json() == {"type": "answer", "text": "B because spread"}


async def test_ask_what_if_diff_computed_in_code(client, monkeypatch):
    from agent import llm
    modified = {**CONTEXT["subject"], "sqft": 2400}
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: _Fake(
        {"type": "what_if", "text": "re-running", "modified_subject": modified}))
    r = await client.post("/api/ask", json={"question": "what if 2400 sqft?",
                                            "context": CONTEXT})
    body = r.json()
    assert body["type"] == "what_if"
    assert body["modified_subject"]["sqft"] == 2400
    assert body["changes"] == [{"field": "sqft", "before": 1850, "after": 2400}]


async def test_ask_what_if_no_actual_change_is_answer(client, monkeypatch):
    from agent import llm
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: _Fake(
        {"type": "what_if", "text": "nothing changed",
         "modified_subject": CONTEXT["subject"]}))
    r = await client.post("/api/ask", json={"question": "what if nothing?",
                                            "context": CONTEXT})
    assert r.json()["type"] == "answer"


async def test_ask_llm_error_degrades(client, monkeypatch):
    from agent import llm

    class Boom:
        async def ainvoke(self, _):
            raise RuntimeError("kaput")

    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: Boom())
    r = await client.post("/api/ask", json={"question": "?", "context": CONTEXT})
    assert r.status_code == 200
    assert "unavailable" in r.json()["text"]
