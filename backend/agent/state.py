"""AgentState contract. Node I/O models land with their tasks (see implementation plan).

Not yet defined (stub references below stay as string annotations until then):
- SearchCriteria  (engine/filters.py, Task 4)  — radius_km, days, sqft_pct, beds_delta
- ScoredComp      (engine/scoring.py, Task 4)  — comp + score + score_parts
- Valuation       (engine/valuation.py, Task 5) — estimate, low, high, confidence, adjustments
- RiskFlag        (engine/risk_rules.py, Task 5)
- ReviewVerdict   (agent/nodes/review.py, Task 7) — address_key, verdict keep|demote|exclude,
  reason, unreviewed
"""

from __future__ import annotations

from typing import TypedDict

from data.schema import PropertyRecord, SubjectProperty


class AgentState(TypedDict, total=False):
    subject: SubjectProperty
    notes_signals: list[str]
    criteria: SearchCriteria
    search_log: list[dict]  # {round, criteria, found, reason}
    candidates: list[PropertyRecord]
    scored: list[ScoredComp]
    reviews: list[ReviewVerdict]
    valuation: Valuation
    risk_flags: list[RiskFlag]
    narrative: str
    errors: list[str]
