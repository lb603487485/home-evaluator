import os

os.environ["AGENT_NO_LLM"] = "1"

import httpx
import pytest

from app.main import app

SUBJECT = dict(community="Evanston", property_type="detached", beds=3, baths=2.5,
               sqft=1850, year_built=2020, lot_sqft=4000, garage_stalls=2, notes="")


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_communities_lists_all_eight_with_stats(client):
    r = await client.get("/api/communities")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 8
    by_name = {d["community"]: d for d in data}
    assert by_name["Evanston"]["sales"] > 300
    assert by_name["Bearspaw"]["sales"] == 5
    for d in data:
        assert d["median_price"] > 100_000
        assert d["types"]


async def test_evaluate_streams_events_in_order(client):
    r = await client.post("/api/evaluate", json=SUBJECT)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    text = r.text
    positions = [text.index(f"event: {name}")
                 for name in ("node", "search_update", "comps", "valuation", "done")]
    assert positions == sorted(positions)
    assert "event: reviews" in text


async def test_invalid_subject_rejected(client):
    r = await client.post("/api/evaluate", json={"community": "Evanston"})
    assert r.status_code == 422
