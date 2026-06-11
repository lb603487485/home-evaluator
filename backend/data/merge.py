"""Join the three sources on address_key with field precedence and conflict records.

Precedence (spec §4): land-titles price > MLS price; assessment year_built > MLS;
MLS interior attrs (sole source). Conflicts beyond tolerance are recorded, never
silently resolved. Multiple transfers keep the latest sale, history recorded.
Assessments cover every property, so the assessment frame drives the join.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from data.schema import Conflict, PropertyRecord
from data.sources import assessments, land_titles, mls
from engine.config import PRICE_CONFLICT_TOL


def _by_key(df: pd.DataFrame) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in df.to_dict("records"):
        grouped.setdefault(row["address_key"], []).append(row)
    return grouped


def merge_sources(mls_df: pd.DataFrame, land_df: pd.DataFrame,
                  assess_df: pd.DataFrame) -> list[PropertyRecord]:
    mls_by, land_by = _by_key(mls_df), _by_key(land_df)
    records = []
    for assess_rows in _by_key(assess_df).values():
        [a] = assess_rows  # one assessment per property
        key = a["address_key"]
        sources = {f: "assessment" for f in
                   ("community", "property_type", "year_built", "assessed_value")}
        conflicts: list[Conflict] = []
        fields: dict = dict(
            address_key=key, address=a["address"], community=a["community"],
            property_type=a["property_type"], lat=a["lat"], lon=a["lon"],
            year_built=a["year_built"], assessed_value=a["assessed_value"],
            lot_sqft=None if pd.isna(a["lot_sqft"]) else int(a["lot_sqft"]),
            beds=None, baths=None, sqft=None,
            sold_price=None, sold_date=None,
        )
        if fields["lot_sqft"] is not None:
            sources["lot_sqft"] = "assessment"

        m = land = None
        if key in mls_by:
            *_, m = sorted(mls_by[key], key=lambda r: r["sold_date"])
            fields["address"] = m["address"]
            for f in ("beds", "beds_bsmt", "baths", "sqft", "garage_stalls"):
                fields[f] = m[f]
                sources[f] = "mls"
            if m["year_built"] != a["year_built"]:
                conflicts.append(Conflict(
                    field="year_built",
                    values={"mls": m["year_built"], "assessment": a["year_built"]},
                    resolved_with="assessment"))
        if key in land_by:
            history = sorted(land_by[key], key=lambda r: r["sold_date"])
            land = history[-1]
            if len(history) > 1:
                conflicts.append(Conflict(
                    field="sold_price",
                    values={r["sold_date"].isoformat(): r["sold_price"] for r in history},
                    resolved_with="latest"))

        if land is not None:
            fields["sold_price"], fields["sold_date"] = land["sold_price"], land["sold_date"]
            sources |= {"sold_price": "land_titles", "sold_date": "land_titles"}
            if (m is not None and m["sold_date"] == land["sold_date"]
                    and abs(m["sold_price"] - land["sold_price"])
                    / land["sold_price"] > PRICE_CONFLICT_TOL):
                conflicts.append(Conflict(
                    field="sold_price",
                    values={"mls": m["sold_price"], "land_titles": land["sold_price"]},
                    resolved_with="land_titles"))
        elif m is not None:
            fields["sold_price"], fields["sold_date"] = m["sold_price"], m["sold_date"]
            sources |= {"sold_price": "mls", "sold_date": "mls"}

        records.append(PropertyRecord(**fields, sources=sources, conflicts=conflicts))
    return records


def build_comps(raw_dir: Path, out_path: Path) -> dict:
    records = merge_sources(mls.load(raw_dir / "mls_sales.csv"),
                            land_titles.load(raw_dir / "land_titles.csv"),
                            assessments.load(raw_dir / "assessments.csv"))
    rows = []
    for rec in records:
        row = rec.model_dump(mode="json")
        row["sources"] = json.dumps(row["sources"])
        row["conflicts"] = json.dumps(row["conflicts"])
        rows.append(row)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out_path, index=False)

    coverage = {1: 0, 2: 0, 3: 0}
    for rec in records:
        coverage[len(set(rec.sources.values()))] += 1
    return dict(rows=len(records),
                sold=sum(r.sold_price is not None for r in records),
                scorable=sum(r.complete_for_comps for r in records),
                conflicts=sum(len(r.conflicts) for r in records),
                coverage=coverage)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).parent
    ap.add_argument("--raw", type=Path, default=base / "raw")
    ap.add_argument("--out", type=Path, default=base / "comps.parquet")
    args = ap.parse_args()
    stats = build_comps(args.raw, args.out)
    pct = {k: f"{v / stats['rows']:.1%}" for k, v in stats["coverage"].items()}
    print(f"{stats['rows']} records → {args.out}")
    print(f"  sold: {stats['sold']} · scorable comps: {stats['scorable']} "
          f"· conflict records: {stats['conflicts']}")
    print(f"  source coverage 3/2/1: {pct[3]} / {pct[2]} / {pct[1]}")


if __name__ == "__main__":
    main()
