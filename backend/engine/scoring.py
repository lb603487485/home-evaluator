"""Similarity scoring 0–100 with a per-dimension breakdown. Pure."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from data.schema import PropertyRecord, SubjectProperty
from engine.config import SCORE_NORM, WEIGHTS
from engine.filters import haversine_km


class ScoredComp(BaseModel):
    comp: PropertyRecord
    score: float
    score_parts: dict[str, float]  # dimension -> points contributed (sums to score)


def _band(delta: float, norm: float) -> float:
    return max(0.0, 1.0 - abs(delta) / norm)


def _lot_closeness(subject: SubjectProperty, comp: PropertyRecord) -> float:
    if subject.lot_sqft is None and comp.lot_sqft is None:
        return 1.0  # both lot-less (e.g. apartments): fully comparable
    if subject.lot_sqft is None or comp.lot_sqft is None:
        return 0.5  # unknown on one side: neutral
    return _band(comp.lot_sqft - subject.lot_sqft, SCORE_NORM["lot_sqft"])


def score_comp(comp: PropertyRecord, subject: SubjectProperty,
               center: tuple[float, float], today: date) -> ScoredComp:
    distance = float(haversine_km(comp.lat, comp.lon, *center))
    beds_baths_delta = (abs(comp.beds - subject.beds)
                        + abs((comp.baths if comp.baths is not None else subject.baths)
                              - subject.baths))
    closeness = {
        "distance": _band(distance, SCORE_NORM["distance_km"]),
        "recency": _band((today - comp.sold_date).days, SCORE_NORM["recency_days"]),
        "sqft": _band(comp.sqft - subject.sqft,
                      SCORE_NORM["sqft_band_pct"] * subject.sqft),
        "beds_baths": _band(beds_baths_delta, SCORE_NORM["beds_baths"]),
        "year_built": _band(comp.year_built - subject.year_built,
                            SCORE_NORM["year_years"]),
        "lot": _lot_closeness(subject, comp),
        "garage": _band(comp.garage_stalls - subject.garage_stalls,
                        SCORE_NORM["garage_stalls"]),
        "same_community": 1.0 if comp.community == subject.community else 0.0,
    }
    parts = {dim: round(WEIGHTS[dim] * closeness[dim], 2) for dim in WEIGHTS}
    return ScoredComp(comp=comp, score=round(sum(parts.values()), 2), score_parts=parts)


def score_comps(candidates: list[PropertyRecord], subject: SubjectProperty,
                center: tuple[float, float], today: date) -> list[ScoredComp]:
    scored = [score_comp(c, subject, center, today) for c in candidates]
    return sorted(scored, key=lambda s: (-s.score, s.comp.address_key))
