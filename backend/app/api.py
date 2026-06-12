"""GET /api/communities · POST /api/evaluate (SSE stream) · POST /api/ask (Q&A)."""

from __future__ import annotations

import json
import time
from datetime import date
from functools import lru_cache
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette import EventSourceResponse

from agent import llm
from agent.graph import build_graph
from app.events import node_event, sse_event
from data.schema import SubjectProperty
from data.store import SyntheticDataSource, ensure_comps

router = APIRouter(prefix="/api")


@lru_cache(maxsize=1)
def get_runtime():
    source = SyntheticDataSource(ensure_comps())
    return source, build_graph(source)


@router.get("/communities")
async def communities() -> list[dict]:
    source, _ = get_runtime()
    return source.communities()


@router.post("/evaluate")
async def evaluate(subject: SubjectProperty) -> EventSourceResponse:
    return EventSourceResponse(_event_stream(subject))


class AskRequest(BaseModel):
    question: str
    history: list[dict] = []  # [{role, text}] prior Q&A, oldest first
    context: dict             # the session's result bundle (stateless backend)


@router.post("/ask")
async def ask(req: AskRequest) -> dict:
    """Grounded Q&A over a completed evaluation; what-ifs return a modified
    subject whose field diff is computed here in code, never trusted from the
    LLM. Degrades to an apology answer on any failure — never 500s."""
    if not llm.llm_enabled():
        return {"type": "answer",
                "text": "Follow-up answers need the LLM (set ANTHROPIC_API_KEY)."}
    try:
        history = "\n".join(f"{m.get('role')}: {m.get('text')}"
                            for m in req.history[-6:])
        message = await llm.get_model("ask", max_tokens=700).ainvoke([
            ("system", llm.load_prompt("ask")),
            ("user", f"TODAY: {date.today()}\n\n"
                     f"CONTEXT:\n{json.dumps(req.context, default=str)}\n\n"
                     f"PRIOR Q&A:\n{history or '(none)'}\n\n"
                     f"QUESTION: {req.question}")])
        data = llm.parse_json_block(llm.message_text(message.content))
        if data.get("type") == "comp_challenge":
            return await _comp_challenge(req, data)
        if data.get("type") != "what_if":
            return {"type": "answer", "text": str(data.get("text", ""))}
        modified = SubjectProperty(**data["modified_subject"])
        original = SubjectProperty(**req.context["subject"])
        changes = [{"field": f, "before": getattr(original, f),
                    "after": getattr(modified, f)}
                   for f in SubjectProperty.model_fields
                   if getattr(original, f) != getattr(modified, f)]
        if not changes:
            return {"type": "answer", "text": str(data.get("text", ""))}
        return {"type": "what_if", "text": str(data.get("text", "")),
                "modified_subject": modified.model_dump(), "changes": changes}
    except Exception as exc:
        return {"type": "answer",
                "text": f"(assistant unavailable — {exc}; the tables above stand)"}


async def _comp_challenge(req: AskRequest, data: dict) -> dict:
    """Reviewer disputes a comp: re-run the SAME review judgment with the claim as
    evidence; only a changed verdict re-runs the engine (valuate + risk rules).
    The human supplies evidence — never the verdict, never the number."""
    from agent.graph import apply_reviews
    from agent.nodes.review import ReviewVerdict, review_comp_node
    from engine.risk_rules import ValuationContext, evaluate_rules
    from engine.scoring import ScoredComp
    from engine.valuation import valuate

    ctx = req.context
    scored = [ScoredComp(**s) for s in ctx.get("scored_full") or []]
    key = data.get("address_key")
    target = next((s for s in scored if s.comp.address_key == key), None)
    if target is None:
        return {"type": "answer",
                "text": "I couldn't match that comp in this evaluation — name it by "
                        "its address or row number."}
    subject = SubjectProperty(**ctx["subject"])
    today = date.fromisoformat(ctx["as_of"])
    claim = str(data.get("claim") or req.question)
    out = await review_comp_node({
        "scored_comp": target, "subject": subject, "today": today,
        "notes_signals": [f"reviewer challenge: {claim}"]})
    [verdict] = out["reviews"]
    if verdict.unreviewed:  # review LLM failed — don't fake a re-review
        return {"type": "answer",
                "text": "(couldn't re-review that comp right now — the original "
                        "verdict stands)"}
    reviews = {r["address_key"]: ReviewVerdict(**r) for r in ctx.get("reviews") or []}
    prior = reviews.get(key)
    changed = verdict.verdict != (prior.verdict if prior else "keep")
    resp = {"type": "comp_challenge", "address_key": key,
            "address": target.comp.address, "verdict": verdict.verdict,
            "reason": verdict.reason, "changed": changed,
            "text": str(data.get("text", ""))}
    if changed:
        reviews[key] = verdict
        kept = apply_reviews(scored, reviews)
        valuation = valuate(kept, subject, today) if kept else None
        vctx = ValuationContext(subject=subject, scored=kept, valuation=valuation,
                                exclusions=ctx.get("exclusions") or [],
                                search_log=ctx.get("search_log") or [], today=today)
        resp["revaluation"] = {
            **(valuation.model_dump(mode="json") if valuation
               else {"estimate": None}),
            "flags": [f.model_dump() for f in evaluate_rules(vctx)]}
    return resp


async def _event_stream(subject: SubjectProperty):
    _, graph = get_runtime()
    run_id = uuid4().hex[:12]
    started = time.perf_counter()
    reviews: list[dict] = []
    exclusions: list[dict] = []
    narrative_streamed = False
    yield node_event("intake", "started")
    try:
        async for mode, chunk in graph.astream({"subject": subject},
                                               stream_mode=["updates", "custom"]):
            if mode == "custom":
                narrative_streamed = True
                yield sse_event("narrative_delta", {"text": chunk})
                continue
            for node, delta in chunk.items():
                delta = delta or {}
                if delta.get("errors"):
                    yield node_event(node, "fallback", detail="; ".join(delta["errors"]))
                if node == "widen":
                    yield node_event("widen", "done", detail=delta.get("widen_reason"))
                elif node == "intake":
                    yield node_event("intake", "done",
                                     detail=", ".join(delta.get("notes_signals") or [])
                                     or None)
                elif node == "search":
                    [entry] = delta["search_log"]
                    # judgment-relevant exclusions only; "incomplete" is data noise
                    exclusions = [e for e in delta.get("exclusions") or []
                                  if e.get("reason") != "incomplete"][:20]
                    yield sse_event("search_update", entry)
                elif node == "score":
                    yield node_event("search", "done")
                    yield sse_event("comps", {
                        "items": [s.model_dump(mode="json")
                                  for s in delta["scored"]],
                        "exclusions": exclusions})
                elif node == "review_comp":
                    reviews.extend(r.model_dump() for r in delta["reviews"])
                    yield sse_event("reviews", {"items": reviews})
                elif node == "valuate":
                    valuation = delta["valuation"]
                    payload = valuation.model_dump(mode="json") if valuation else None
                    yield sse_event("valuation", {
                        **(payload or {"estimate": None}),
                        "flags": [f.model_dump() for f in delta["risk_flags"]]})
                elif node == "narrate":
                    # tokens already streamed via the custom channel; re-emit only
                    # when the node produced text without streaming (fallback path)
                    if delta.get("narrative") and not narrative_streamed:
                        yield sse_event("narrative_delta", {"text": delta["narrative"]})
                    yield node_event("narrate", "done")
    except Exception as exc:  # surface, don't 500 a half-sent stream
        yield sse_event("error", {"message": str(exc), "recoverable": False})
        return
    yield sse_event("done", {
        "run_id": run_id,
        "timings": {"total_s": round(time.perf_counter() - started, 2)}})
