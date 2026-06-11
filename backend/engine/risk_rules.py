"""Risk-flag rule registry. Each rule: ValuationContext -> RiskFlag | None.

Extensibility contract: append a callable to RISK_RULES and it is evaluated —
no other wiring. Rules are pure and ordered; evaluation never raises.
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Literal

from pydantic import BaseModel, Field

from data.schema import SubjectProperty
from engine.config import CONFIDENCE, MIN_COMPS, STALE_DAYS
from engine.scoring import ScoredComp
from engine.valuation import Valuation


class RiskFlag(BaseModel):
    code: str
    severity: Literal["info", "caution", "warning"]
    message: str
    evidence: dict = Field(default_factory=dict)


class ValuationContext(BaseModel):
    subject: SubjectProperty
    scored: list[ScoredComp]
    valuation: Valuation
    exclusions: list[dict] = Field(default_factory=list)  # {address_key, reason, ...}
    search_log: list[dict] = Field(default_factory=list)  # {round, criteria, found, reason}
    today: date


def _thin_comps(ctx: ValuationContext) -> RiskFlag | None:
    n = len(ctx.scored)
    if n < MIN_COMPS:
        return RiskFlag(code="THIN_COMPS", severity="warning",
                        message=f"Only {n} comparable sales support this estimate "
                                f"(minimum {MIN_COMPS} preferred).",
                        evidence={"n_comps": n, "min_comps": MIN_COMPS})
    return None


def _high_dispersion(ctx: ValuationContext) -> RiskFlag | None:
    v = ctx.valuation
    iqr_ratio = (v.high - v.low) / v.estimate
    if iqr_ratio >= CONFIDENCE["C"]["min_iqr"]:
        return RiskFlag(code="HIGH_DISPERSION", severity="caution",
                        message=f"Adjusted comp prices spread {iqr_ratio:.0%} of the "
                                "estimate; the market for this profile is volatile.",
                        evidence={"iqr_ratio": round(iqr_ratio, 3)})
    return None


def _non_arms_length_excluded(ctx: ValuationContext) -> RiskFlag | None:
    hits = [e for e in ctx.exclusions if e.get("reason") == "non_arms_length"]
    if hits:
        return RiskFlag(code="NON_ARMS_LENGTH_EXCLUDED", severity="info",
                        message=f"Excluded {len(hits)} suspected non-arm's-length "
                                "transfer(s) (price far below assessed value).",
                        evidence={"addresses": [e.get("address_key") for e in hits]})
    return None


def _data_conflict(ctx: ValuationContext) -> RiskFlag | None:
    hits = [s.comp.address_key for s in ctx.scored
            if any(c.resolved_with != "latest" for c in s.comp.conflicts)]
    if hits:
        return RiskFlag(code="DATA_CONFLICT", severity="caution",
                        message=f"{len(hits)} comp(s) had conflicting source values; "
                                "precedence rules applied (see provenance).",
                        evidence={"addresses": hits})
    return None


def _extrapolation(ctx: ValuationContext) -> RiskFlag | None:
    if not ctx.scored:
        return None
    sqfts = [s.comp.sqft for s in ctx.scored]
    if not min(sqfts) <= ctx.subject.sqft <= max(sqfts):
        return RiskFlag(code="EXTRAPOLATION", severity="caution",
                        message="Subject size falls outside the comp set; the "
                                "estimate extrapolates beyond observed sales.",
                        evidence={"subject_sqft": ctx.subject.sqft,
                                  "comp_range": [min(sqfts), max(sqfts)]})
    return None


def _stale_comps(ctx: ValuationContext) -> RiskFlag | None:
    if not ctx.scored:
        return None
    ages = sorted((ctx.today - s.comp.sold_date).days for s in ctx.scored)
    median_age = ages[len(ages) // 2]
    if median_age > STALE_DAYS:
        return RiskFlag(code="STALE_COMPS", severity="caution",
                        message=f"Median comp sale is {median_age} days old; time "
                                "adjustments carry more of the estimate than usual.",
                        evidence={"median_days": median_age, "stale_days": STALE_DAYS})
    return None


def _widened_search(ctx: ValuationContext) -> RiskFlag | None:
    widened = [e for e in ctx.search_log if e.get("round", 0) > 0]
    if widened:
        return RiskFlag(code="WIDENED_SEARCH", severity="info",
                        message=f"Search criteria were widened {len(widened)} time(s) "
                                "to find enough comps.",
                        evidence={"rounds": len(widened),
                                  "reasons": [e.get("reason") for e in widened]})
    return None


RISK_RULES: list[Callable[[ValuationContext], RiskFlag | None]] = [
    _thin_comps, _high_dispersion, _non_arms_length_excluded, _data_conflict,
    _extrapolation, _stale_comps, _widened_search,
]


def evaluate_rules(ctx: ValuationContext) -> list[RiskFlag]:
    return [flag for rule in RISK_RULES if (flag := rule(ctx)) is not None]
