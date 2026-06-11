"""Canonical property schema — the contract shared by ingestion, engine, and agent."""

from __future__ import annotations

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


class SubjectProperty(BaseModel):
    community: str
    property_type: str
    beds: int
    baths: float
    sqft: int
    year_built: int
    lot_sqft: int | None = None
    garage_stalls: int = 0
    notes: str = ""


# normalize_address(raw: str) -> str  — implemented in Task 1 (TDD)
