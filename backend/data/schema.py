"""Canonical property schema — the contract shared by ingestion, engine, and agent."""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Conflict(BaseModel):
    field: str
    values: dict[str, float | int | str]
    resolved_with: str


class PropertyRecord(BaseModel):
    address_key: str  # normalized join key
    address: str  # display form
    community: str
    property_type: Literal["detached", "semi", "townhouse", "apartment"]
    beds: int | None  # above grade
    beds_bsmt: int = 0
    baths: float | None
    sqft: int | None
    lot_sqft: int | None
    year_built: int | None
    garage_stalls: int = 0
    lat: float
    lon: float
    sold_price: int | None  # None for assessment-only rows
    sold_date: date | None
    assessed_value: int | None
    sources: dict[str, str] = Field(default_factory=dict)  # field -> "mls" | "land_titles" | "assessment"
    conflicts: list[Conflict] = Field(default_factory=list)

    @property
    def complete_for_comps(self) -> bool:
        """Scorable as a comp; incomplete records still feed non-arm's-length detection."""
        return None not in (self.sqft, self.beds, self.sold_price, self.sold_date)


class SubjectProperty(BaseModel):
    community: str
    address: str = ""  # display + cross-check only; never feeds the engine math
    property_type: str
    beds: int
    baths: float
    sqft: int
    year_built: int
    lot_sqft: int | None = None
    garage_stalls: int = 0
    notes: str = ""


_CITY_RE = re.compile(r",\s*CALGARY(?:\s*,?\s*(?:AB|ALBERTA))?\s*$")
_UNIT_RE = re.compile(r"^\s*(?:#|UNIT\b|APT\b)\s*(\w+)\s*[,\-]?\s*")

_ABBREV = {
    "AVENUE": "AVE", "AV": "AVE",
    "STREET": "ST",
    "WY": "WAY",
    "DRIVE": "DR",
    "ROAD": "RD",
    "BOULEVARD": "BLVD",
    "CRESCENT": "CRES",
    "PLACE": "PL",
    "COURT": "CT",
    "NORTHWEST": "NW", "NORTHEAST": "NE", "SOUTHWEST": "SW", "SOUTHEAST": "SE",
}


def normalize_address(raw: str) -> str:
    """Canonical join key: uppercase, city dropped, unit prefix unified,
    suffix/direction abbreviated, punctuation stripped."""
    s = raw.upper()
    s = _CITY_RE.sub("", s)
    unit = None
    if m := _UNIT_RE.match(s):
        unit = m.group(1)
        s = s[m.end():]
    s = re.sub(r"[^\w\s]", " ", s)
    tokens = [_ABBREV.get(t, t) for t in s.split()]
    if unit:
        tokens.insert(0, unit)
    return " ".join(tokens)
