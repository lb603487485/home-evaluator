"""LLM-node wiring tests with fake models — no API calls.

Covers: tool-choice widening, accept_results, JSON verdict parsing, intake signals,
and the degradation guarantee (LLM raising ⇒ deterministic fallback, never an error).
"""

from datetime import date

import pytest
from langchain_core.messages import AIMessage

from agent import llm
from agent.graph import build_graph
from agent.nodes.intake import intake_node
from agent.nodes.review import review_comp_node
from agent.nodes.search import route_after_widen, widen_node
from data.schema import PropertyRecord, SubjectProperty
from data.store import SyntheticDataSource, ensure_comps
from engine.filters import SearchCriteria
from engine.scoring import score_comps

TODAY = date(2026, 6, 1)

SUBJECT = SubjectProperty(community="Evanston", property_type="detached", beds=3,
                          baths=2.5, sqft=1850, year_built=2020, lot_sqft=4000,
                          garage_stalls=2, notes="backs onto golf course")


class FakeModel:
    def __init__(self, message):
        self.message = message

    def bind_tools(self, tools, tool_choice=None):
        return self

    async def ainvoke(self, _messages):
        if isinstance(self.message, Exception):
            raise self.message
        return self.message


@pytest.fixture
def llm_on(monkeypatch):
    monkeypatch.delenv("AGENT_NO_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def install(message):
        monkeypatch.setattr(llm, "get_model", lambda node, **kw: FakeModel(message))
    return install


def comp(key="c1"):
    return PropertyRecord(address_key=key, address=key, community="Evanston",
                          property_type="detached", beds=3, baths=2.5, sqft=1850,
                          lot_sqft=4000, year_built=2020, garage_stalls=2,
                          lat=51.174, lon=-114.119, sold_price=620_000,
                          sold_date=TODAY, assessed_value=600_000)


WIDEN_STATE = dict(subject=SUBJECT, criteria=SearchCriteria(), candidates=[],
                   search_log=[dict(round=0, criteria={}, found=0, reason="initial")],
                   today=TODAY)


class TestWiden:
    async def test_llm_tool_call_picks_move(self, llm_on):
        llm_on(AIMessage(content="", tool_calls=[
            {"name": "relax_sqft", "args": {"reason": "unusual size for the area"},
             "id": "1"}]))
        out = await widen_node(WIDEN_STATE)
        assert out["criteria"].sqft_pct == 0.35
        assert "unusual size" in out["widen_reason"]

    async def test_accept_results_stops_widening(self, llm_on):
        llm_on(AIMessage(content="", tool_calls=[
            {"name": "accept_results", "args": {"reason": "market is simply thin"},
             "id": "1"}]))
        out = await widen_node(WIDEN_STATE)
        assert out.get("widen_accepted") is True
        assert route_after_widen({**WIDEN_STATE, **out}) == "score"

    async def test_llm_failure_falls_back_to_deterministic_order(self, llm_on):
        llm_on(RuntimeError("api down"))
        out = await widen_node(WIDEN_STATE)
        assert out["criteria"].days == 270  # first deterministic move: extend_days
        assert out.get("widen_accepted") is not True


class TestReview:
    async def test_json_verdict_parsed(self, llm_on):
        llm_on(AIMessage(content='{"verdict": "exclude", "reason": "price far below '
                                 'assessment suggests non-arm\'s-length"}'))
        [scored] = score_comps([comp()], SUBJECT, (51.174, -114.119), TODAY)
        out = await review_comp_node({"scored_comp": scored, "subject": SUBJECT,
                                      "notes_signals": []})
        [verdict] = out["reviews"]
        assert verdict.verdict == "exclude"
        assert verdict.unreviewed is False

    async def test_failure_keeps_unreviewed(self, llm_on):
        llm_on(RuntimeError("api down"))
        [scored] = score_comps([comp()], SUBJECT, (51.174, -114.119), TODAY)
        out = await review_comp_node({"scored_comp": scored, "subject": SUBJECT,
                                      "notes_signals": []})
        [verdict] = out["reviews"]
        assert verdict.verdict == "keep"
        assert verdict.unreviewed is True


class TestIntake:
    async def test_signals_extracted_from_notes(self, llm_on):
        llm_on(AIMessage(content='```json\n{"signals": ["backs onto golf course"], '
                                 '"concerns": []}\n```'))
        out = await intake_node({"subject": SUBJECT, "today": TODAY})
        assert out["notes_signals"] == ["backs onto golf course"]

    async def test_failure_yields_empty_signals(self, llm_on):
        llm_on(RuntimeError("api down"))
        out = await intake_node({"subject": SUBJECT, "today": TODAY})
        assert out["notes_signals"] == []


async def test_graph_completes_when_llm_always_raises(llm_on):
    llm_on(RuntimeError("api down"))
    graph = build_graph(SyntheticDataSource(ensure_comps()))
    out = await graph.ainvoke({"subject": SUBJECT, "today": TODAY})
    assert out["valuation"] is not None
    assert out["narrative"] == ""
    assert all(r.unreviewed for r in out["reviews"])
    assert out["errors"]  # degradation was recorded, not hidden
