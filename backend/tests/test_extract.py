import json
import os

os.environ["AGENT_NO_LLM"] = "1"

import httpx
import pytest

from app.main import app


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


async def test_extract_no_llm_degrades(client):
    r = await client.post("/api/extract", json={"text": "88 9 St NE Calgary"})
    assert r.status_code == 200
    body = r.json()
    assert body["fields"] == {} and body["community"] is None


async def test_extract_fields_and_inferred_community(client, monkeypatch):
    from agent import llm
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: _Fake({
        "fields": {"address": "88 9 St NE", "beds": 3, "baths": 2.5, "sqft": 1400,
                   "year_built": 1952, "garage_stalls": 1,
                   "notes": "backs onto the river", "bogus_key": "dropped"},
        "community": {"value": "Bridgeland",
                      "reason": "T2E postal prefix and numbered NE street"},
    }))
    r = await client.post("/api/extract", json={
        "text": "88 9 St NE, Calgary, AB T2E 4E1, 3 bed 2.5 bath ~1400 sqft "
                "built 1952, single garage, backs onto the river"})
    body = r.json()
    assert body["fields"]["beds"] == 3
    assert body["fields"]["year_built"] == 1952
    assert "bogus_key" not in body["fields"]          # whitelist enforced in code
    assert body["community"]["value"] == "Bridgeland"
    assert body["community"]["source"] == "inferred"  # name not literally in text
    assert body["community"]["reason"]


async def test_extract_named_community_source(client, monkeypatch):
    from agent import llm
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: _Fake({
        "fields": {"address": "310 Evanston Dr NW"},
        "community": {"value": "Evanston", "reason": "street name"},
    }))
    r = await client.post("/api/extract", json={"text": "310 Evanston Dr NW, 3 bed"})
    assert r.json()["community"]["source"] == "named"


async def test_extract_unknown_community_rejected(client, monkeypatch):
    from agent import llm
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: _Fake({
        "fields": {},
        "community": {"value": "Springbank", "reason": "not in the dataset"},
    }))
    r = await client.post("/api/extract", json={"text": "some Springbank acreage"})
    assert r.json()["community"] is None              # constrained to known list


async def test_extract_llm_error_degrades(client, monkeypatch):
    from agent import llm

    class Boom:
        async def ainvoke(self, _):
            raise RuntimeError("kaput")

    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: Boom())
    r = await client.post("/api/extract", json={"text": "x"})
    assert r.status_code == 200 and r.json()["fields"] == {}
