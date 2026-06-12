"""S5: chat grounding — config-generated methodology + market stats in /api/ask,
plus the two prompt hardenings (what-if latest-message scoping, challenge skepticism)."""

import json
import os

os.environ["AGENT_NO_LLM"] = "1"

import httpx
import pytest

from app.main import app
from engine import config

SUBJECT = dict(community="Evanston", address="", property_type="detached",
               beds=3, baths=2.5, sqft=1850, year_built=2020, lot_sqft=4000,
               garage_stalls=2, notes="")


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- methodology block: generated from config so it can't drift ---

def test_methodology_states_similarity_weights():
    from engine.methodology import methodology_block
    text = methodology_block()
    for dim, weight in config.WEIGHTS.items():
        assert f"{dim} {weight}" in text


def test_methodology_states_adjustment_rates():
    from engine.methodology import methodology_block
    text = methodology_block()
    assert f"{config.ADJ['ppsf_marginal']:.0%}" in text
    for key in ("bed", "bath", "garage", "age_per_year", "age_cap"):
        assert f"${config.ADJ[key]:,}" in text
    assert f"{config.ADJ['lot_deadband']:,} sqft" in text  # deadband is area, not $


def test_methodology_states_confidence_cuts():
    from engine.methodology import methodology_block
    text = methodology_block()
    assert f"≥{config.CONFIDENCE['A']['min_comps']} comps" in text
    assert f"≤{config.CONFIDENCE['A']['max_iqr']:.0%}" in text
    assert f"≥{config.CONFIDENCE['C']['min_iqr']:.0%}" in text
    assert "weighted median" in text


def test_methodology_states_search_and_widening_caps():
    from engine.methodology import methodology_block
    text = methodology_block()
    assert f"{config.FILTER_DEFAULTS['radius_km']} km" in text
    assert f"{config.FILTER_DEFAULTS['days']} days" in text
    assert f"≤{config.MAX_WIDEN_ROUNDS} rounds" in text
    assert f"{config.SCORE_NORM['recency_days']:.0f}" in text


def test_methodology_covers_every_registered_risk_rule():
    from engine.methodology import RISK_RULE_MEANINGS, methodology_block
    from engine.risk_rules import RISK_RULES
    registered = {rule.__name__.lstrip("_").upper() for rule in RISK_RULES}
    assert set(RISK_RULE_MEANINGS) == registered  # new rule ⇒ this fails loudly
    text = methodology_block()
    for code in registered:
        assert code in text


# --- /api/ask carries the grounding blocks ---

class _Recorder:
    def __init__(self):
        self.messages = None

    async def ainvoke(self, messages):
        self.messages = messages

        class M:
            content = json.dumps({"type": "answer", "text": "ok"})
        return M()


async def test_ask_context_carries_methodology_and_market_stats(client, monkeypatch):
    from agent import llm
    rec = _Recorder()
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: rec)
    r = await client.post("/api/ask", json={"question": "how do adjustments work?",
                                            "context": {"subject": SUBJECT}})
    assert r.json() == {"type": "answer", "text": "ok"}
    user_msg = dict(rec.messages)["user"]
    assert "METHODOLOGY" in user_msg
    assert f"${config.ADJ['bed']:,}" in user_msg
    assert "MARKET STATS" in user_msg
    assert "median_price" in user_msg
    for community in config.MARKET_TREND_QOQ:  # all 8, not just the subject's
        assert community in user_msg


# --- prompt hardenings (the contract lines must exist verbatim-ish) ---

def test_ask_prompt_scopes_what_if_to_latest_message():
    from agent import llm
    text = llm.load_prompt("ask").lower()
    assert "latest message" in text


def test_ask_prompt_answers_method_questions_from_grounding():
    from agent import llm
    text = llm.load_prompt("ask")
    assert "METHODOLOGY" in text and "MARKET STATS" in text


def test_review_prompt_treats_challenges_as_unverified():
    from agent import llm
    text = llm.load_prompt("review").lower()
    assert "reviewer challenge" in text
    assert "unverified" in text
