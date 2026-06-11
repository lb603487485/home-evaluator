"""Search: fetch comps for current criteria; widen (≤ MAX_WIDEN_ROUNDS) when thin.

The widening choice is genuine LLM tool-calling — bind_tools over the widening moves
plus accept_results, tool_choice="any", each call carrying a logged reason.
Fallback: deterministic move order from WIDENING_MOVES.
"""

import json

from pydantic import BaseModel, Field

from agent import llm
from engine.config import MAX_WIDEN_ROUNDS, MIN_COMPS, WIDENING_MOVES
from engine.filters import apply_move

_REASON = Field(description="One sentence explaining why this move fits the gap; "
                            "it is logged verbatim in the audit trail")


class extend_days(BaseModel):
    """Extend the sold-date window by 90 days (cap 365) — recent sales are too few but the area is right."""
    reason: str = _REASON


class widen_radius(BaseModel):
    """Multiply the search radius by 1.5 (cap 5 km) — comps likely sit just outside the current radius."""
    reason: str = _REASON


class relax_sqft(BaseModel):
    """Relax the size band to ±35% — the subject's size is unusual for its area."""
    reason: str = _REASON


class relax_beds(BaseModel):
    """Allow ±2 bedrooms — bed count is binding in a market with varied layouts."""
    reason: str = _REASON


class accept_results(BaseModel):
    """Stop widening and proceed with the comps found; the valuation will carry flags."""
    reason: str = _REASON


WIDEN_TOOLS = [extend_days, widen_radius, relax_sqft, relax_beds, accept_results]


def make_search_node(source):
    async def search_node(state: dict) -> dict:
        subject, criteria, today = state["subject"], state["criteria"], state["today"]
        candidates = await source.fetch(subject, criteria, today)
        exclusions = await source.excluded(subject, criteria, today)
        round_n = len(state.get("search_log") or [])
        reason = "initial criteria" if round_n == 0 else state["widen_reason"]
        entry = dict(round=round_n, criteria=criteria.model_dump(),
                     found=len(candidates), reason=reason)
        return {"candidates": candidates, "exclusions": exclusions,
                "search_log": [entry]}
    return search_node


def route_after_search(state: dict) -> str:
    enough = len(state["candidates"]) >= MIN_COMPS
    exhausted = len(state["search_log"]) > MAX_WIDEN_ROUNDS
    return "score" if enough or exhausted else "widen"


def route_after_widen(state: dict) -> str:
    return "score" if state.get("widen_accepted") else "search"


def _deterministic_widen(state: dict) -> dict:
    moves = list(WIDENING_MOVES)
    move = moves[(len(state["search_log"]) - 1) % len(moves)]
    return {"criteria": apply_move(state["criteria"], move),
            "widen_reason": f"{move}: only {len(state['candidates'])} comps found"}


async def widen_node(state: dict) -> dict:
    if not llm.llm_enabled():
        return _deterministic_widen(state)
    try:
        model = llm.get_model("search").bind_tools(WIDEN_TOOLS, tool_choice="any")
        message = await model.ainvoke([
            ("system", llm.load_prompt("search")),
            ("user", json.dumps({
                "subject": state["subject"].model_dump(),
                "current_criteria": state["criteria"].model_dump(),
                "rounds_so_far": state["search_log"],
                "comps_found": len(state["candidates"]),
                "min_comps_wanted": MIN_COMPS,
            }, default=str, indent=2))])
        call = message.tool_calls[0]
        move, reason = call["name"], call["args"].get("reason", "")
        if move == "accept_results":
            return {"widen_accepted": True, "widen_reason": f"accept_results: {reason}"}
        return {"criteria": apply_move(state["criteria"], move),
                "widen_reason": f"{move}: {reason}"}
    except Exception as exc:
        return _deterministic_widen(state) | {
            "errors": [f"widen: LLM fallback ({exc})"]}
