"""The six-node LangGraph: intake → search (⇄ widen) → score → review fan-out →
valuate → narrate. LLM = judgment + language only; every number comes from the engine."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.nodes.intake import intake_node
from agent.nodes.narrate import narrate_node
from agent.nodes.review import fan_out_reviews, review_comp_node
from agent.nodes.search import (make_search_node, make_widen_node,
                                route_after_search, route_after_widen)
from agent.state import AgentState
from data.store import SyntheticDataSource
from engine.config import TOP_N_REVIEW
from engine.risk_rules import ValuationContext, evaluate_rules
from engine.scoring import score_comps
from engine.valuation import valuate


def make_score_node(source):
    async def score_node(state: dict) -> dict:
        center = source.community_center(state["subject"].community)
        scored = score_comps(state["candidates"], state["subject"], center,
                             state["today"])
        return {"scored": scored}
    return score_node


async def valuate_node(state: dict) -> dict:
    reviews = {r.address_key: r for r in state.get("reviews") or []}
    kept = []
    for scored in state["scored"][:TOP_N_REVIEW]:
        review = reviews.get(scored.comp.address_key)
        if review and review.verdict == "exclude":
            continue
        if review and review.verdict == "demote":
            scored = scored.model_copy(update={"score": round(scored.score * 0.5, 2)})
        kept.append(scored)
    valuation = valuate(kept, state["subject"], state["today"]) if kept else None
    ctx = ValuationContext(subject=state["subject"], scored=kept, valuation=valuation,
                           exclusions=state.get("exclusions") or [],
                           search_log=state.get("search_log") or [],
                           today=state["today"])
    return {"valuation": valuation, "risk_flags": evaluate_rules(ctx)}


def make_graph():
    """Zero-arg factory for LangGraph Studio / `langgraph dev` (see langgraph.json)."""
    return build_graph()


def build_graph(source: SyntheticDataSource | None = None):
    source = source or SyntheticDataSource()
    g = StateGraph(AgentState)
    g.add_node("intake", intake_node)
    g.add_node("search", make_search_node(source))
    g.add_node("widen", make_widen_node(source))
    g.add_node("score", make_score_node(source))
    g.add_node("review_comp", review_comp_node)
    g.add_node("valuate", valuate_node)
    g.add_node("narrate", narrate_node)

    g.add_edge(START, "intake")
    g.add_edge("intake", "search")
    g.add_conditional_edges("search", route_after_search, ["score", "widen"])
    g.add_conditional_edges("widen", route_after_widen, ["search", "score"])
    g.add_conditional_edges("score", fan_out_reviews, ["review_comp", "valuate"])
    g.add_edge("review_comp", "valuate")
    g.add_edge("valuate", "narrate")
    g.add_edge("narrate", END)
    return g.compile()
