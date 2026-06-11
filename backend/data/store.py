"""CompSource protocol + the synthetic implementation over comps.parquet.

Production story: N adapters implementing CompSource, queried with asyncio.gather.
"""

from __future__ import annotations

import json
from datetime import date
from math import isnan
from pathlib import Path
from typing import Protocol

import pandas as pd

from data.schema import PropertyRecord, SubjectProperty
from engine.filters import SearchCriteria, apply_filters, find_exclusions

DEFAULT_RAW = Path(__file__).parent / "raw"
DEFAULT_PARQUET = Path(__file__).parent / "comps.parquet"


class CompSource(Protocol):
    async def fetch(self, subject: SubjectProperty, criteria: SearchCriteria,
                    today: date) -> list[PropertyRecord]: ...


def ensure_comps(parquet: Path = DEFAULT_PARQUET, raw: Path = DEFAULT_RAW,
                 seed: int = 42) -> Path:
    """Build raw CSVs and comps.parquet if missing (idempotent, seeded)."""
    if parquet.exists():
        return parquet
    from data.generate import generate_world
    from data.merge import build_comps
    if not (raw / "mls_sales.csv").exists():
        raw.mkdir(parents=True, exist_ok=True)
        for name, df in generate_world(seed=seed).frames.items():
            df.to_csv(raw / f"{name}.csv", index=False)
    build_comps(raw, parquet)
    return parquet


class SyntheticDataSource:
    def __init__(self, parquet_path: Path = DEFAULT_PARQUET):
        self._path = Path(parquet_path)
        self._df: pd.DataFrame | None = None

    def _frame(self) -> pd.DataFrame:
        if self._df is None:
            df = pd.read_parquet(self._path)
            df["sold_date"] = df["sold_date"].map(
                lambda s: date.fromisoformat(s) if isinstance(s, str) else None)
            df["sources"] = df["sources"].map(json.loads)
            df["conflicts"] = df["conflicts"].map(json.loads)
            self._df = df
        return self._df

    def communities(self) -> list[dict]:
        sold = self._frame()
        sold = sold[sold["sold_price"].notna()]
        return [dict(community=name, sales=int(len(group)),
                     median_price=int(group["sold_price"].median()),
                     types=sorted(group["property_type"].unique()))
                for name, group in sold.groupby("community")]

    def community_center(self, community: str) -> tuple[float, float]:
        rows = self._frame()
        rows = rows[rows["community"] == community]
        return float(rows["lat"].median()), float(rows["lon"].median())

    async def fetch(self, subject: SubjectProperty, criteria: SearchCriteria,
                    today: date) -> list[PropertyRecord]:
        df = apply_filters(self._frame(), subject,
                           self.community_center(subject.community), criteria, today)
        return [PropertyRecord.model_validate(_clean(row))
                for row in df.to_dict("records")]

    async def excluded(self, subject: SubjectProperty, criteria: SearchCriteria,
                       today: date) -> list[dict]:
        return find_exclusions(self._frame(), subject,
                               self.community_center(subject.community), criteria, today)


def _clean(row: dict) -> dict:
    return {k: None if isinstance(v, float) and isnan(v) else v for k, v in row.items()}
