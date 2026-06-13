"""Review: Send fan-out worker judging each top comp.

Worker prompt carries the comp + score breakdown + deterministic pre-checks
(price/assessed ratio, source conflicts, quick-flip suspicion). Per-worker failure
degrades to keep + unreviewed — one bad call never sinks the run.
"""

from datetime import date, timedelta
from typing import Literal

from langgraph.types import Send
from pydantic import BaseModel

from agent import llm
from data.schema import PropertyRecord
from engine.config import (FLIP_GAIN_SUSPECT, FLIP_WINDOW_DAYS,
                            NON_ARMS_LENGTH_RATIO, TOP_N_REVIEW)

VERDICTS = ("keep", "demote", "exclude")


class ReviewVerdict(BaseModel):
    address_key: str
    verdict: Literal["keep", "demote", "exclude"] = "keep"
    reason: str = ""
    unreviewed: bool = False


def prechecks(comp: PropertyRecord) -> dict:
    ratio = (round(comp.sold_price / comp.assessed_value, 2)
             if comp.sold_price and comp.assessed_value else None)
    source_conflicts = [c.model_dump() for c in comp.conflicts
                        if c.resolved_with != "latest"]
    flip_suspect = False
    for c in comp.conflicts:
        if c.resolved_with != "latest":
            continue
        sales = sorted((date.fromisoformat(d), p) for d, p in c.values.items())
        for (d1, p1), (d2, p2) in zip(sales, sales[1:]):
            if d2 - d1 < timedelta(days=FLIP_WINDOW_DAYS) and p2 / p1 > FLIP_GAIN_SUSPECT:
                flip_suspect = True
    return {"price_to_assessed_ratio": ratio,
            "non_arms_length_threshold": NON_ARMS_LENGTH_RATIO,
            "source_conflicts": source_conflicts,
            "quick_flip_suspect": flip_suspect}


def fan_out_reviews(state: dict):
    top = state["scored"][:TOP_N_REVIEW]
    if not top:
        return "valuate"
    return [Send("review_comp", {"scored_comp": s, "subject": state["subject"],
                                 "notes_signals": state.get("notes_signals") or [],
                                 "today": state["today"]})
            for s in top]


def _fallback(scored, note: str) -> dict:
    return {"reviews": [ReviewVerdict(address_key=scored.comp.address_key,
                                      verdict="keep", reason=note, unreviewed=True)]}


async def review_comp_node(payload: dict) -> dict:
    scored = payload["scored_comp"]
    if not llm.llm_enabled():
        return _fallback(scored, "kept without LLM review")
    try:
        message = await llm.get_model("review", max_tokens=300).ainvoke([
            ("system", llm.load_prompt("review")),
            ("user", f"TODAY: {payload['today']}\n\n"
             + "SUBJECT:\n" + payload["subject"].model_dump_json(indent=2)
             + "\nINTAKE SIGNALS: " + (", ".join(payload["notes_signals"]) or "none")
             + "\n\nCOMP:\n" + scored.comp.model_dump_json(indent=2)
             + "\n\nSIMILARITY: " + str(scored.score)
             + " parts=" + str(scored.score_parts)
             + "\n\nPRE-CHECKS:\n" + str(prechecks(scored.comp)))])
        data = llm.parse_json_block(llm.message_text(message.content))
        if data.get("verdict") not in VERDICTS:
            raise ValueError(f"bad verdict: {data.get('verdict')!r}")
        verdict = ReviewVerdict(address_key=scored.comp.address_key,
                                verdict=data["verdict"],
                                reason=str(data.get("reason", ""))[:300])
        return {"reviews": [verdict]}
    except Exception as exc:
        return _fallback(scored, "kept without LLM review") | {
            "errors": [f"review {scored.comp.address_key}: LLM fallback ({exc})"]}
