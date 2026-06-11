"""GET /api/communities · POST /api/evaluate (SSE stream of agent progress)."""

from __future__ import annotations

import time
from functools import lru_cache
from uuid import uuid4

from fastapi import APIRouter
from sse_starlette import EventSourceResponse

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


async def _event_stream(subject: SubjectProperty):
    _, graph = get_runtime()
    run_id = uuid4().hex[:12]
    started = time.perf_counter()
    reviews: list[dict] = []
    yield node_event("intake", "started")
    try:
        async for mode, chunk in graph.astream({"subject": subject},
                                               stream_mode=["updates", "custom"]):
            if mode == "custom":
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
                    yield sse_event("search_update", entry)
                elif node == "score":
                    yield node_event("search", "done")
                    yield sse_event("comps", {"items": [
                        s.model_dump(mode="json") for s in delta["scored"]]})
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
                    if delta.get("narrative"):
                        yield sse_event("narrative_delta", {"text": delta["narrative"]})
                    yield node_event("narrate", "done")
    except Exception as exc:  # surface, don't 500 a half-sent stream
        yield sse_event("error", {"message": str(exc), "recoverable": False})
        return
    yield sse_event("done", {
        "run_id": run_id,
        "timings": {"total_s": round(time.perf_counter() - started, 2)}})
