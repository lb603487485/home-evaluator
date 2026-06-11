"""Hard comp filters + widening moves. Pure: no LLM, no clock, no I/O."""

from __future__ import annotations

from datetime import date
from math import cos, radians

import numpy as np
import pandas as pd
from pydantic import BaseModel

from data.schema import PropertyRecord, SubjectProperty
from engine.config import FILTER_DEFAULTS, NON_ARMS_LENGTH_RATIO, WIDENING_MOVES


class SearchCriteria(BaseModel):
    radius_km: float = FILTER_DEFAULTS["radius_km"]
    days: int = FILTER_DEFAULTS["days"]
    sqft_pct: float = FILTER_DEFAULTS["sqft_pct"]
    beds_delta: int = FILTER_DEFAULTS["beds_delta"]


def haversine_km(lat, lon, lat0: float, lon0: float):
    lat, lon = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    dlat, dlon = lat - radians(lat0), lon - radians(lon0)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat) * cos(radians(lat0)) * np.sin(dlon / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def records_frame(records: list[PropertyRecord]) -> pd.DataFrame:
    return pd.DataFrame([r.model_dump() for r in records])


def apply_filters(df: pd.DataFrame, subject: SubjectProperty,
                  center: tuple[float, float], criteria: SearchCriteria,
                  today: date) -> pd.DataFrame:
    complete = (df["sqft"].notna() & df["beds"].notna()
                & df["sold_price"].notna() & df["sold_date"].notna())
    df = df[(df["property_type"] == subject.property_type) & complete]
    distance = haversine_km(df["lat"], df["lon"], *center)
    days_ago = df["sold_date"].map(lambda d: (today - d).days)
    mask = ((distance <= criteria.radius_km)
            & (days_ago <= criteria.days)
            & ((df["sqft"].astype(float) - subject.sqft).abs()
               <= criteria.sqft_pct * subject.sqft)
            & ((df["beds"].astype(float) - subject.beds).abs() <= criteria.beds_delta))
    return df[mask]


def find_exclusions(df: pd.DataFrame, subject: SubjectProperty,
                    center: tuple[float, float], criteria: SearchCriteria,
                    today: date) -> list[dict]:
    """Sales inside the search box that cannot serve as comps, with the reason."""
    sold = (df["sold_price"].notna() & df["sold_date"].notna()
            & (df["property_type"] == subject.property_type))
    df = df[sold]
    distance = haversine_km(df["lat"], df["lon"], *center)
    days_ago = df["sold_date"].map(lambda d: (today - d).days)
    box = df[(distance <= criteria.radius_km) & (days_ago <= criteria.days)]
    exclusions = []
    for row in box.to_dict("records"):
        if row["assessed_value"] and row["sold_price"] / row["assessed_value"] \
                < NON_ARMS_LENGTH_RATIO:
            exclusions.append(dict(
                address_key=row["address_key"], reason="non_arms_length",
                ratio=round(row["sold_price"] / row["assessed_value"], 2)))
        elif pd.isna(row["sqft"]) or pd.isna(row["beds"]):
            exclusions.append(dict(address_key=row["address_key"], reason="incomplete"))
    return exclusions


def apply_move(criteria: SearchCriteria, move: str) -> SearchCriteria:
    """Pure: returns a new SearchCriteria; each move respects its cap."""
    c = criteria.model_copy()
    if move == "extend_days":
        step, cap = WIDENING_MOVES["extend_days"]
        c.days = min(c.days + step, cap)
    elif move == "widen_radius":
        factor, cap = WIDENING_MOVES["widen_radius"]
        c.radius_km = min(c.radius_km * factor, cap)
    elif move == "relax_sqft":
        (c.sqft_pct,) = WIDENING_MOVES["relax_sqft"]
    elif move == "relax_beds":
        (c.beds_delta,) = WIDENING_MOVES["relax_beds"]
    else:
        raise ValueError(f"unknown widening move: {move}")
    return c
