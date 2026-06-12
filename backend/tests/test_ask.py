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


def _comp(key: str, price: int, score: float) -> dict:
    return {
        "comp": {
            "address_key": key, "address": key.title(), "community": "Evanston",
            "property_type": "detached", "beds": 3, "beds_bsmt": 0, "baths": 2.5,
            "sqft": 1850, "lot_sqft": 4000, "year_built": 2020, "garage_stalls": 2,
            "lat": 51.17, "lon": -114.12, "sold_price": price,
            "sold_date": "2026-05-01", "assessed_value": price, "sources": {},
            "conflicts": [],
        },
        "score": score, "score_parts": {},
    }


CHALLENGE_CONTEXT = {
    **CONTEXT,
    "as_of": "2026-06-11",
    "search_log": [],
    "exclusions": [],
    "reviews": [{"address_key": "100 A ST NW", "verdict": "keep", "reason": "",
                 "unreviewed": False},
                {"address_key": "200 B ST NW", "verdict": "keep", "reason": "",
                 "unreviewed": False}],
    "scored_full": [_comp("100 A ST NW", 600_000, 90.0),
                    _comp("200 B ST NW", 700_000, 85.0)],
}


class _Seq:
    """One fake model shared by the ask call and the re-review call."""

    def __init__(self, payloads):
        self.payloads = list(payloads)

    async def ainvoke(self, _messages):
        payload = self.payloads.pop(0)

        class M:
            content = json.dumps(payload)
        return M()


async def test_comp_challenge_flip_recomputes_valuation(client, monkeypatch):
    from agent import llm
    seq = _Seq([
        {"type": "comp_challenge", "address_key": "200 B ST NW",
         "text": "re-reviewing", "claim": "backs onto a highway"},
        {"verdict": "exclude", "reason": "highway exposure not comparable"},
    ])
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: seq)
    r = await client.post("/api/ask", json={
        "question": "comp 2 backs onto a highway", "context": CHALLENGE_CONTEXT})
    body = r.json()
    assert body["type"] == "comp_challenge"
    assert body["verdict"] == "exclude" and body["changed"] is True
    # only the 600k comp remains; engine recomputes from it alone
    assert body["revaluation"]["estimate"] == round(600_000 + sum(
        body["revaluation"]["adjustments"][0]["adjustments"].values()))
    assert body["revaluation"]["confidence"] == "C"  # 1 comp → thin
    assert any(f["code"] == "THIN_COMPS" for f in body["revaluation"]["flags"])


async def test_comp_challenge_upheld_no_revaluation(client, monkeypatch):
    from agent import llm
    seq = _Seq([
        {"type": "comp_challenge", "address_key": "200 B ST NW",
         "text": "re-reviewing", "claim": "seems too expensive"},
        {"verdict": "keep", "reason": "price reflects size; similarity is sound"},
    ])
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: seq)
    r = await client.post("/api/ask", json={
        "question": "comp 2 seems too expensive", "context": CHALLENGE_CONTEXT})
    body = r.json()
    assert body["type"] == "comp_challenge"
    assert body["changed"] is False
    assert "revaluation" not in body


async def test_comp_challenge_unknown_comp_degrades(client, monkeypatch):
    from agent import llm
    seq = _Seq([{"type": "comp_challenge", "address_key": "999 NOWHERE",
                 "text": "re-reviewing", "claim": "x"}])
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: seq)
    r = await client.post("/api/ask", json={
        "question": "comp 99 is wrong", "context": CHALLENGE_CONTEXT})
    assert r.json()["type"] == "answer"
