"""Review: Send fan-out worker judging each top comp.

Task 6: deterministic fallback only — keep everything, marked unreviewed.
Task 7 adds the LLM verdict; per-worker failure degrades to this fallback.
"""

from typing import Literal

from langgraph.types import Send
from pydantic import BaseModel

from engine.config import TOP_N_REVIEW


class ReviewVerdict(BaseModel):
    address_key: str
    verdict: Literal["keep", "demote", "exclude"] = "keep"
    reason: str = ""
    unreviewed: bool = False


def fan_out_reviews(state: dict):
    top = state["scored"][:TOP_N_REVIEW]
    if not top:
        return "valuate"
    return [Send("review_comp", {"scored_comp": s}) for s in top]


async def review_comp_node(payload: dict) -> dict:
    scored = payload["scored_comp"]
    verdict = ReviewVerdict(address_key=scored.comp.address_key, verdict="keep",
                            reason="kept without LLM review", unreviewed=True)
    return {"reviews": [verdict]}
