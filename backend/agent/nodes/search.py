"""Search: fetch comps for current criteria; widen (≤ MAX_WIDEN_ROUNDS) when thin.

Task 6: deterministic widening in WIDENING_MOVES order.
Task 7 replaces widen_node's move choice with genuine LLM tool-calling.
"""

from engine.config import MAX_WIDEN_ROUNDS, MIN_COMPS, WIDENING_MOVES
from engine.filters import apply_move


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


async def widen_node(state: dict) -> dict:
    moves = list(WIDENING_MOVES)
    move = moves[(len(state["search_log"]) - 1) % len(moves)]
    return {"criteria": apply_move(state["criteria"], move),
            "widen_reason": f"{move}: only {len(state['candidates'])} comps found"}
