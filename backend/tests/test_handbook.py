"""S6: methodology spent two more ways — structured data for UI popovers
(GET /api/methodology) and the auto-generated docs/handbook.md (drift-guarded)."""

import os
from pathlib import Path

os.environ["AGENT_NO_LLM"] = "1"

import httpx
import pytest

from app.main import app
from engine import config

HANDBOOK = Path(__file__).resolve().parent.parent.parent / "docs" / "handbook.md"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- structured form for the popovers ---

def test_methodology_data_covers_registry_and_grades():
    from engine.methodology import methodology_data
    from engine.risk_rules import RISK_RULES
    data = methodology_data()
    codes = {rule.__name__.lstrip("_").upper() for rule in RISK_RULES}
    assert set(data["flags"]) == codes
    assert set(data["confidence"]) == {"A", "B", "C"}
    # the popover strings carry the real thresholds
    assert f"≥{config.CONFIDENCE['A']['min_comps']} comps" in data["confidence"]["A"]
    assert f"≥{config.CONFIDENCE['C']['min_iqr']:.0%}" in data["confidence"]["C"]


async def test_api_methodology_endpoint(client):
    r = await client.get("/api/methodology")
    assert r.status_code == 200
    body = r.json()
    assert "STALE_COMPS" in body["flags"]
    assert "B" in body["confidence"]


# --- the handbook document ---

def test_handbook_markdown_is_generated_reference():
    from engine.methodology import handbook_markdown
    text = handbook_markdown()
    assert "do not edit by hand" in text.lower()
    for dim, weight in config.WEIGHTS.items():
        assert f"| {dim} | {weight} |" in text  # weights as a table
    assert f"${config.ADJ['bed']:,}" in text
    for community in config.MARKET_TREND_QOQ:
        assert community in text
    word_count = len(text.split())
    assert word_count < 800  # a reference card, not prose — bloat means drift risk


def test_handbook_file_is_fresh():
    """Drift guard: the checked-in handbook must match the generator exactly.
    Touch a config constant without regenerating -> this fails."""
    from engine.methodology import handbook_markdown
    assert HANDBOOK.exists(), "run: uv run python -m engine.methodology"
    assert HANDBOOK.read_text() == handbook_markdown()
