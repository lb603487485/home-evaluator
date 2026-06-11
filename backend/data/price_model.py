"""Ground-truth price model — single source of truth shared by the generator and eval.

price = base_ppsf · sqft
        + premiums for attrs beyond the community-typical configuration
        − age depreciation (capped) + lot premium beyond typical lot
        × community quarterly trend factor (anchored at TREND_ANCHOR, older = cheaper)

The generator multiplies by (1 + ε), ε ~ N(0, NOISE_SD); true_price itself is deterministic.
"""

from __future__ import annotations

from datetime import date
from typing import Mapping

BASE_PPSF = {  # (community, type) -> $/sqft; types absent = not generated
    "Beltline": {"apartment": 420},
    "Bridgeland": {"apartment": 440, "townhouse": 390},
    "Killarney": {"semi": 460, "detached": 510},
    "Tuscany": {"detached": 350},
    "Evanston": {"detached": 330, "townhouse": 310},
    "Auburn Bay": {"detached": 360, "townhouse": 330},
    "Aspen Woods": {"detached": 520},
    "Bearspaw": {"detached": 480},
}

PREMIUMS = dict(bed=9_000, bath=7_000, garage=11_000, bsmt_finished=25_000)
AGE_DEP_PER_YEAR, AGE_DEP_CAP = 850, 22_000
LOT_PER_SQFT = 2.2  # beyond community-typical lot
TREND_QoQ = {c: 0.012 for c in BASE_PPSF} | {"Beltline": 0.018, "Bearspaw": 0.006}
NOISE_SD = 0.04
NOISE_SD_OVERRIDES = {"Aspen Woods": 0.10}

TREND_ANCHOR = date(2026, 6, 1)  # generation "today"; sales this day get factor 1.0
DAYS_PER_QUARTER = 91.25

# Community-typical configuration: BASE_PPSF prices this config; premiums price deviations.
TYPICAL = {  # (community, type) -> dict(beds, baths, garage, lot)
    ("Beltline", "apartment"): dict(beds=2, baths=2.0, garage=1, lot=None),
    ("Bridgeland", "apartment"): dict(beds=2, baths=2.0, garage=1, lot=None),
    ("Bridgeland", "townhouse"): dict(beds=3, baths=2.5, garage=1, lot=1800),
    ("Killarney", "semi"): dict(beds=4, baths=3.5, garage=2, lot=3000),
    ("Killarney", "detached"): dict(beds=3, baths=2.0, garage=1, lot=6000),
    ("Tuscany", "detached"): dict(beds=4, baths=3.0, garage=2, lot=4500),
    ("Evanston", "detached"): dict(beds=3, baths=2.5, garage=2, lot=4000),
    ("Evanston", "townhouse"): dict(beds=3, baths=2.5, garage=1, lot=1900),
    ("Auburn Bay", "detached"): dict(beds=4, baths=3.0, garage=2, lot=4400),
    ("Auburn Bay", "townhouse"): dict(beds=3, baths=2.5, garage=1, lot=1900),
    ("Aspen Woods", "detached"): dict(beds=4, baths=3.5, garage=3, lot=7000),
    ("Bearspaw", "detached"): dict(beds=4, baths=3.5, garage=3, lot=160_000),
}


def true_price(attrs: Mapping, sold_date: date) -> int:
    """Deterministic market value of `attrs` on `sold_date`.

    Required keys: community, property_type, sqft, year_built.
    Optional (default = community-typical): beds, baths, garage_stalls, lot_sqft, beds_bsmt.
    """
    community, ptype = attrs["community"], attrs["property_type"]
    typ = TYPICAL[(community, ptype)]
    raw = BASE_PPSF[community][ptype] * attrs["sqft"]
    raw += (attrs.get("beds") or typ["beds"]) * PREMIUMS["bed"] - typ["beds"] * PREMIUMS["bed"]
    raw += ((attrs.get("baths") or typ["baths"]) - typ["baths"]) * PREMIUMS["bath"]
    garage = attrs.get("garage_stalls")
    raw += ((typ["garage"] if garage is None else garage) - typ["garage"]) * PREMIUMS["garage"]
    if attrs.get("beds_bsmt"):
        raw += PREMIUMS["bsmt_finished"]
    age = max(0, sold_date.year - attrs["year_built"])
    raw -= min(age * AGE_DEP_PER_YEAR, AGE_DEP_CAP)
    lot = attrs.get("lot_sqft")
    if lot is not None and typ["lot"] is not None:
        raw += (lot - typ["lot"]) * LOT_PER_SQFT
    quarters = (TREND_ANCHOR - sold_date).days / DAYS_PER_QUARTER
    return round(raw * (1 + TREND_QoQ[community]) ** -quarters)
