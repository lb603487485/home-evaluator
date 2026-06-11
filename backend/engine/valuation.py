"""Adjustment-based valuation: per-comp adjustment ladder → similarity-weighted
median estimate with weighted P25–P75 range and A/B/C confidence. Pure."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

from data.schema import SubjectProperty
from engine.config import ADJ, CONFIDENCE, DAYS_PER_QUARTER, MARKET_TREND_QOQ
from engine.scoring import ScoredComp


class AdjustedComp(BaseModel):
    address_key: str
    address: str
    sold_price: int
    sold_date: date
    score: float
    adjustments: dict[str, float]  # term -> $ amount toward the subject
    adjusted_price: float


class Valuation(BaseModel):
    estimate: int
    low: int
    high: int
    confidence: Literal["A", "B", "C"]
    adjustments: list[AdjustedComp]


def adjust_comp(scored: ScoredComp, subject: SubjectProperty, today: date) -> AdjustedComp:
    c = scored.comp
    quarters = (today - c.sold_date).days / DAYS_PER_QUARTER
    adj = {
        "time": c.sold_price * ((1 + MARKET_TREND_QOQ[c.community]) ** quarters - 1),
        "sqft": (subject.sqft - c.sqft) * ADJ["ppsf_marginal"] * (c.sold_price / c.sqft),
        "beds": (subject.beds - c.beds) * ADJ["bed"],
        "baths": ((subject.baths - c.baths) * ADJ["bath"]
                  if c.baths is not None else 0.0),
        "garage": (subject.garage_stalls - c.garage_stalls) * ADJ["garage"],
        "age": max(-ADJ["age_cap"],
                   min(ADJ["age_cap"],
                       (subject.year_built - c.year_built) * ADJ["age_per_year"])),
    }
    if subject.lot_sqft is not None and c.lot_sqft is not None:
        delta = subject.lot_sqft - c.lot_sqft
        beyond = max(0, abs(delta) - ADJ["lot_deadband"])
        adj["lot"] = (beyond if delta > 0 else -beyond) * ADJ["lot_per_sqft"]
    else:
        adj["lot"] = 0.0
    adj = {term: round(v, 2) for term, v in adj.items()}
    return AdjustedComp(address_key=c.address_key, address=c.address,
                        sold_price=c.sold_price, sold_date=c.sold_date,
                        score=scored.score, adjustments=adj,
                        adjusted_price=round(c.sold_price + sum(adj.values()), 2))


def _weighted_percentile(pairs: list[tuple[float, float]], q: float) -> float:
    """pairs sorted by price; returns the first price where cumulative weight ≥ q."""
    target = q * sum(w for _, w in pairs)
    cum = 0.0
    for price, w in pairs:
        cum += w
        if cum >= target:
            return price
    return pairs[-1][0]


def valuate(scored: list[ScoredComp], subject: SubjectProperty, today: date) -> Valuation:
    adjusted = [adjust_comp(s, subject, today) for s in scored]
    pairs = sorted((a.adjusted_price, a.score) for a in adjusted)
    estimate = _weighted_percentile(pairs, 0.5)
    low, high = _weighted_percentile(pairs, 0.25), _weighted_percentile(pairs, 0.75)
    iqr_ratio = (high - low) / estimate
    mean_sim = sum(s.score for s in scored) / len(scored)

    a, c = CONFIDENCE["A"], CONFIDENCE["C"]
    if len(scored) <= c["max_comps"] or iqr_ratio >= c["min_iqr"]:
        confidence = "C"
    elif (len(scored) >= a["min_comps"] and iqr_ratio <= a["max_iqr"]
          and mean_sim >= a["min_sim"]):
        confidence = "A"
    else:
        confidence = "B"
    return Valuation(estimate=int(round(estimate)), low=int(round(low)),
                     high=int(round(high)), confidence=confidence, adjustments=adjusted)
