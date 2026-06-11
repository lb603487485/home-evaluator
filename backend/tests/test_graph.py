from datetime import date

import pytest

from agent.graph import build_graph
from data.generate import generate_world
from data.schema import SubjectProperty
from data.store import SyntheticDataSource, ensure_comps

TODAY = date(2026, 6, 1)

EVANSTON = SubjectProperty(community="Evanston", property_type="detached", beds=3,
                           baths=2.5, sqft=1850, year_built=2020, lot_sqft=4000,
                           garage_stalls=2)
BEARSPAW = SubjectProperty(community="Bearspaw", property_type="detached", beds=4,
                           baths=3.5, sqft=3000, year_built=2005, lot_sqft=150_000,
                           garage_stalls=3)


@pytest.fixture(scope="module")
def graph():
    return build_graph(SyntheticDataSource(ensure_comps()))


async def test_evanston_runs_end_to_end_without_widening(graph):
    out = await graph.ainvoke({"subject": EVANSTON, "today": TODAY})
    assert out["valuation"] is not None
    assert out["valuation"].low <= out["valuation"].estimate <= out["valuation"].high
    assert len(out["scored"]) >= 5
    assert [e["round"] for e in out["search_log"]] == [0]  # no widening needed
    assert out["reviews"] and all(r.unreviewed for r in out["reviews"])  # LLM-off mode
    assert out["narrative"] == ""


async def test_bearspaw_widens_with_caps_and_flags(graph):
    out = await graph.ainvoke({"subject": BEARSPAW, "today": TODAY})
    log = out["search_log"]
    assert len(log) >= 2  # at least one widening round
    assert log[0]["found"] < 5
    for entry in log:
        c = entry["criteria"]
        assert c["days"] <= 365
        assert c["radius_km"] <= 5.0
        assert c["sqft_pct"] <= 0.35
        assert c["beds_delta"] <= 2
    assert all(entry["reason"] for entry in log)
    flag_codes = {f.code for f in out["risk_flags"]}
    assert {"WIDENED_SEARCH", "THIN_COMPS"} <= flag_codes
    assert out["valuation"] is not None  # thin ⇒ low confidence, not no answer
    assert out["valuation"].confidence == "C"


async def test_accepts_plain_json_input(graph):
    # LangGraph Studio / SDK clients submit raw JSON, not pydantic objects
    out = await graph.ainvoke({"subject": EVANSTON.model_dump(),
                               "today": TODAY.isoformat()})
    assert out["valuation"] is not None


async def test_non_arms_length_never_reaches_scored_set(graph):
    private = set(generate_world(seed=42).manifest["private"])
    out = await graph.ainvoke({"subject": EVANSTON, "today": TODAY})
    assert private.isdisjoint({s.comp.address_key for s in out["scored"]})
