"""Narrate: streamed appraiser-style explanation of the valuation.

Streams tokens through the graph's custom channel (SSE narrative_delta).
Fallback: empty narrative — the tables speak.
"""

import json

from langgraph.config import get_stream_writer

from agent import llm


def _data_block(state: dict) -> str:
    valuation = state["valuation"]
    return json.dumps({
        "today": state["today"],
        "subject": state["subject"].model_dump(),
        "intake_signals": state.get("notes_signals") or [],
        "search_log": state.get("search_log") or [],
        "exclusions": state.get("exclusions") or [],
        "kept_comps": [a.model_dump() for a in valuation.adjustments],
        "review_verdicts": [r.model_dump() for r in state.get("reviews") or []],
        "valuation": {"estimate": valuation.estimate, "low": valuation.low,
                      "high": valuation.high, "confidence": valuation.confidence},
        "risk_flags": [f.model_dump() for f in state.get("risk_flags") or []],
    }, default=str, indent=2)


async def narrate_node(state: dict) -> dict:
    if not llm.llm_enabled() or not state.get("valuation"):
        return {"narrative": ""}
    try:
        writer = get_stream_writer()
        model = llm.get_model("narrate", max_tokens=1500)
        parts: list[str] = []
        async for chunk in model.astream([
                ("system", llm.load_prompt("narrate")),
                ("user", "DATA BLOCK:\n" + _data_block(state))]):
            text = llm.message_text(chunk.content)
            if text:
                parts.append(text)
                writer(text)
        return {"narrative": "".join(parts)}
    except Exception as exc:
        return {"narrative": "", "errors": [f"narrate: LLM fallback ({exc})"]}
