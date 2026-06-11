"""AgentState — the contract every node reads from and writes to."""

from __future__ import annotations

import operator
from datetime import date
from typing import Annotated, TypedDict

from agent.nodes.review import ReviewVerdict
from data.schema import PropertyRecord, SubjectProperty
from engine.filters import SearchCriteria
from engine.risk_rules import RiskFlag
from engine.scoring import ScoredComp
from engine.valuation import Valuation


class AgentState(TypedDict, total=False):
    subject: SubjectProperty
    today: date
    notes_signals: list[str]
    criteria: SearchCriteria
    widen_reason: str
    search_log: Annotated[list[dict], operator.add]  # {round, criteria, found, reason}
    candidates: list[PropertyRecord]
    exclusions: list[dict]  # {address_key, reason, ...}
    scored: list[ScoredComp]
    reviews: Annotated[list[ReviewVerdict], operator.add]  # Send fan-out accumulates
    valuation: Valuation | None
    risk_flags: list[RiskFlag]
    narrative: str
    errors: Annotated[list[str], operator.add]
