"""SSE event shapes — mirrored in frontend/src/types.ts.

node {node, status: started|done|fallback, detail?} ·
search_update {round, criteria, found, reason} · comps {items} · reviews {items} ·
valuation {estimate, low, high, confidence, flags, adjustments} ·
narrative_delta {text} · done {run_id, timings} · error {message, recoverable}
"""

import json

from sse_starlette import ServerSentEvent


def sse_event(event_type: str, payload: dict) -> ServerSentEvent:
    return ServerSentEvent(event=event_type, data=json.dumps(payload, default=str))


def node_event(node: str, status: str, detail: str | None = None) -> ServerSentEvent:
    payload = {"node": node, "status": status}
    if detail:
        payload["detail"] = detail
    return sse_event("node", payload)
