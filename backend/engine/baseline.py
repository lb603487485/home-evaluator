"""Market-norm baseline: median $/sqft over recent same-market sales. Pure.

The honest AVM stand-in — a transparent yardstick, not a trained model. The
BASELINE_DIVERGENCE risk rule compares the comp-based estimate against
median_ppsf × subject_sqft and flags disagreement; it never replaces the estimate.
"""

from __future__ import annotations

from statistics import median

from data.schema import PropertyRecord
from engine.config import BASELINE_MIN_SAMPLE


def market_ppsf(records: list[PropertyRecord]) -> tuple[float | None, int]:
    """(median $/sqft, sample size) over records with both price and size.

    Returns (None, n) below BASELINE_MIN_SAMPLE — a thin market's yardstick
    would be noise, so the divergence rule stays silent rather than flagging it.
    """
    ppsf = [r.sold_price / r.sqft for r in records
            if r.sold_price and r.sqft]
    if len(ppsf) < BASELINE_MIN_SAMPLE:
        return None, len(ppsf)
    return round(median(ppsf), 2), len(ppsf)
