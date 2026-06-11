"""Seeded synthetic Calgary world → three differently-shaped source CSVs (spec §3).

Planted edge cases: non-arm's-length private transfers, thin Bearspaw market,
Aspen Woods noise, two quick flips, MLS price/year conflicts, stale Tuscany pocket.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import timedelta
from datetime import date as Date
from math import cos, pi, radians, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

from data.price_model import NOISE_SD, NOISE_SD_OVERRIDES, TREND_ANCHOR, true_price
from data.schema import normalize_address

ASSESS_DATE = Date(2026, 1, 1)   # city assessment valuation date
WINDOW_DAYS = 730
PRIVATE_RATE = 0.02
CONFLICT_RATE = 0.05
PRIVATE_MULT = (0.50, 0.65)      # keeps price/assessed safely below the 0.75 detector
FLIP_GAIN = 1.25
STALE_POCKET_SIZE, STALE_POCKET_SALES, STALE_MIN_DAYS = 60, 25, 150
POCKET_OFFSET = (0.020, -0.036)  # ~3.4 km from Tuscany centroid: outside default 2 km radius
KM_PER_DEG_LAT = 111.32

# Per community: centroid, jitter radius, and per-type volumes + attribute ranges.
# Street suffixes stay within normalize_address's abbreviation table.
COMMUNITIES = {
    "Beltline": dict(
        centroid=(51.0420, -114.0715), radius_km=0.8,
        types={"apartment": dict(
            sales=500, properties=1150, sqft=(450, 1150), beds=(1, 2),
            baths=(1.0, 2.0), year=(1998, 2023), lot=None, garage=(0, 1), bsmt_p=0.0,
            buildings=[(880, "12 Ave SW"), (1010, "12 Ave SW"), (625, "13 Ave SW"),
                       (734, "13 Ave SW"), (902, "11 Ave SW"), (1188, "11 Ave SW"),
                       (517, "14 Ave SW"), (1320, "14 Ave SW")])}),
    "Bridgeland": dict(
        centroid=(51.0525, -114.0405), radius_km=0.9,
        types={
            "apartment": dict(
                sales=220, properties=520, sqft=(500, 1200), beds=(1, 2),
                baths=(1.0, 2.0), year=(2002, 2024), lot=None, garage=(0, 1), bsmt_p=0.0,
                buildings=[(120, "McDougall Rd NE"), (340, "McDougall Rd NE"),
                           (88, "Centre Ave NE"), (210, "Centre Ave NE"),
                           (415, "1 Ave NE")]),
            "townhouse": dict(
                sales=80, properties=190, sqft=(1150, 1650), beds=(2, 3),
                baths=(2.0, 3.5), year=(2008, 2024), lot=(1500, 2200), garage=(1, 2),
                bsmt_p=0.2, streets=["9 St NE", "Bridge Cres NE"])}),
    "Killarney": dict(
        centroid=(51.0375, -114.1260), radius_km=1.0,
        types={
            "semi": dict(
                sales=200, properties=460, sqft=(1400, 2000), beds=(3, 4),
                baths=(2.5, 3.5), year=(2008, 2025), lot=(2700, 3300), garage=(1, 2),
                bsmt_p=0.25, streets=["26 Ave SW", "28 Ave SW", "Kildare Cres SW"]),
            "detached": dict(
                sales=150, properties=380, sqft=(950, 2300), beds=(2, 4),
                baths=(1.0, 3.0), year=(1952, 2024), lot=(5500, 6300), garage=(0, 2),
                bsmt_p=0.35, streets=["29 Ave SW", "30 Ave SW", "37 St SW"])}),
    "Tuscany": dict(
        centroid=(51.1255, -114.2350), radius_km=1.0,
        types={"detached": dict(
            sales=450, properties=1050, sqft=(1400, 2500), beds=(3, 5),
            baths=(2.5, 3.5), year=(1997, 2012), lot=(3800, 5600), garage=(2, 2),
            bsmt_p=0.35,
            streets=["Tuscany Ravine Rd NW", "Tuscany Hills Way NW",
                     "Tuscany Springs Blvd NW", "Tuscany Vista Rd NW"])}),
    "Evanston": dict(
        centroid=(51.1740, -114.1190), radius_km=1.1,
        types={
            "detached": dict(
                sales=400, properties=900, sqft=(1500, 2350), beds=(3, 4),
                baths=(2.0, 3.0), year=(2013, 2024), lot=(3300, 4800), garage=(2, 2),
                bsmt_p=0.35,
                streets=["Evanston Way NW", "Evansridge Ct NW",
                         "Evansborough Cres NW", "Evanston Dr NW"]),
            "townhouse": dict(
                sales=100, properties=240, sqft=(1150, 1500), beds=(2, 3),
                baths=(1.5, 2.5), year=(2014, 2024), lot=(1600, 2200), garage=(1, 1),
                bsmt_p=0.1, streets=["Evanscrest Way NW", "Evansglen Dr NW"])}),
    "Auburn Bay": dict(
        centroid=(50.8895, -113.9595), radius_km=1.1,
        types={
            "detached": dict(
                sales=300, properties=700, sqft=(1450, 2650), beds=(3, 5),
                baths=(2.5, 3.5), year=(2007, 2021), lot=(3500, 5300), garage=(2, 2),
                bsmt_p=0.35,
                streets=["Auburn Bay Blvd SE", "Auburn Shores Way SE",
                         "Auburn Sound Cres SE", "Auburn Glen Dr SE"]),
            "townhouse": dict(
                sales=100, properties=240, sqft=(1150, 1550), beds=(2, 3),
                baths=(1.5, 2.5), year=(2009, 2022), lot=(1600, 2200), garage=(1, 1),
                bsmt_p=0.1, streets=["Auburn Meadows Way SE", "Auburn Crest Pl SE"])}),
    "Aspen Woods": dict(
        centroid=(51.0455, -114.2080), radius_km=1.2,
        types={"detached": dict(
            sales=150, properties=380, sqft=(2200, 4300), beds=(3, 5),
            baths=(3.0, 5.0), year=(2004, 2020), lot=(5000, 9500), garage=(2, 3),
            bsmt_p=0.4,
            streets=["Aspen Summit Dr SW", "Aspen Stone Blvd SW", "Aspen Ridge Way SW"])}),
    "Bearspaw": dict(
        centroid=(51.1850, -114.3650), radius_km=5.0,
        types={"detached": dict(
            sales=5, properties=80, sqft=(2400, 4600), beds=(3, 5),
            baths=(3.0, 4.5), year=(1988, 2020), lot=(85_000, 240_000), garage=(3, 3),
            bsmt_p=0.5,
            streets=["Bearspaw Meadows Way NW", "Church Ranches Blvd NW",
                     "Glenbow Rd NW"])}),
}

ASSESS_ABBREV = {"WAY": "WY", "AVE": "AV"}


@dataclass
class World:
    frames: dict[str, pd.DataFrame]
    manifest: dict[str, list[str]]


def _round500(x: float) -> int:
    return int(round(x / 500.0) * 500)


def _assess_form(civic: str) -> str:
    tokens = civic.upper().replace(",", "").replace("#", "UNIT ").split()
    return " ".join(ASSESS_ABBREV.get(t, t) for t in tokens)


def _jitter(rng, centroid, radius_km):
    lat0, lon0 = centroid
    r = radius_km * sqrt(rng.uniform())
    th = rng.uniform() * 2 * pi
    return (round(lat0 + r * np.sin(th) / KM_PER_DEG_LAT, 6),
            round(lon0 + r * np.cos(th) / (KM_PER_DEG_LAT * cos(radians(lat0))), 6))


def _gen_properties(rng) -> list[dict]:
    props = []
    for community, cfg in COMMUNITIES.items():
        for ptype, t in cfg["types"].items():
            for i in range(t["properties"]):
                if "buildings" in t:
                    bldg_num, street = t["buildings"][i % len(t["buildings"])]
                    k = i // len(t["buildings"])
                    unit = 100 * (1 + k // 8) + k % 8 + 1
                    civic = f"#{unit}, {bldg_num} {street}"
                else:
                    streets = t["streets"]
                    street = streets[i % len(streets)]
                    civic = f"{7 + 4 * (i // len(streets))} {street}"
                pocket = community == "Tuscany" and i < STALE_POCKET_SIZE
                if pocket:
                    center = (cfg["centroid"][0] + POCKET_OFFSET[0],
                              cfg["centroid"][1] + POCKET_OFFSET[1])
                    lat, lon = _jitter(rng, center, 0.35)
                else:
                    lat, lon = _jitter(rng, cfg["centroid"], cfg["radius_km"])
                attrs = dict(
                    community=community, property_type=ptype,
                    sqft=int(rng.integers(t["sqft"][0], t["sqft"][1] + 1)),
                    beds=int(rng.integers(t["beds"][0], t["beds"][1] + 1)),
                    beds_bsmt=int(rng.uniform() < t["bsmt_p"]),
                    baths=float(rng.integers(int(t["baths"][0] * 2),
                                             int(t["baths"][1] * 2) + 1)) / 2,
                    year_built=int(rng.integers(t["year"][0], t["year"][1] + 1)),
                    lot_sqft=(int(rng.integers(t["lot"][0], t["lot"][1] + 1))
                              if t["lot"] else None),
                    garage_stalls=int(rng.integers(t["garage"][0], t["garage"][1] + 1)),
                )
                assessed = _round500(
                    true_price(attrs, ASSESS_DATE)
                    * float(np.clip(rng.normal(0.97, 0.02), 0.93, 1.01)))
                props.append(dict(civic=civic, lat=lat, lon=lon, pocket=pocket,
                                  assessed=assessed, **attrs))
    return props


def _sale(rng, prop: dict, days_back: int) -> dict:
    sold = TREND_ANCHOR - timedelta(days=days_back)
    sd = NOISE_SD_OVERRIDES.get(prop["community"], NOISE_SD)
    eps = float(np.clip(rng.normal(0, sd), -2.2 * sd, 2.2 * sd))
    return dict(prop=prop, sold_date=sold,
                price=_round500(true_price(prop, sold) * (1 + eps)),
                private=False, flip=False)


def _gen_sales(rng, props: list[dict]) -> list[dict]:
    by_group: dict[tuple, list[dict]] = {}
    for p in props:
        by_group.setdefault((p["community"], p["property_type"]), []).append(p)
    sales = []
    for community, cfg in COMMUNITIES.items():
        for ptype, t in cfg["types"].items():
            group = by_group[(community, ptype)]
            if community == "Bearspaw":  # thin and spread out in time
                for j, idx in enumerate(rng.choice(len(group), t["sales"], replace=False)):
                    sales.append(_sale(rng, group[idx],
                                       40 + 160 * j + int(rng.integers(-30, 31))))
            elif community == "Tuscany":  # stale pocket sells, but never recently
                pocket = [p for p in group if p["pocket"]]
                rest = [p for p in group if not p["pocket"]]
                for idx in rng.choice(len(pocket), STALE_POCKET_SALES, replace=False):
                    sales.append(_sale(rng, pocket[idx],
                                       int(rng.integers(STALE_MIN_DAYS, WINDOW_DAYS))))
                for idx in rng.choice(len(rest), t["sales"] - STALE_POCKET_SALES,
                                      replace=False):
                    sales.append(_sale(rng, rest[idx], int(rng.integers(0, WINDOW_DAYS))))
            else:
                for idx in rng.choice(len(group), t["sales"], replace=False):
                    sales.append(_sale(rng, group[idx], int(rng.integers(0, WINDOW_DAYS))))
    return sales


def _plant_flips(rng, sales: list[dict]) -> list[dict]:
    flipped = []
    for community in ("Evanston", "Tuscany"):
        sale = next(s for s in sales if s["prop"]["community"] == community
                    and s["prop"]["property_type"] == "detached"
                    and not s["prop"]["pocket"])
        d1 = TREND_ANCHOR - timedelta(days=int(rng.integers(250, 600)))
        eps = float(np.clip(rng.normal(0, NOISE_SD), -2.2 * NOISE_SD, 2.2 * NOISE_SD))
        sale.update(flip=True, sold_date=d1,
                    price=_round500(true_price(sale["prop"], d1) * (1 + eps)))
        sales.append(dict(prop=sale["prop"],
                          sold_date=d1 + timedelta(days=int(rng.integers(60, 170))),
                          price=_round500(sale["price"] * FLIP_GAIN),
                          private=False, flip=True))
        flipped.append(sale["prop"])
    return flipped


def _plant_private(rng, sales: list[dict]) -> list[dict]:
    eligible = [s for s in sales if not s["flip"] and s["prop"]["community"] != "Bearspaw"]
    chosen = rng.choice(len(eligible), int(PRIVATE_RATE * len(eligible)), replace=False)
    for idx in chosen:
        s = eligible[idx]
        s["private"] = True
        s["price"] = _round500(true_price(s["prop"], s["sold_date"])
                               * rng.uniform(*PRIVATE_MULT))
    return [eligible[idx]["prop"] for idx in chosen]


def generate_world(seed: int) -> World:
    rng = np.random.default_rng(seed)
    props = _gen_properties(rng)
    sales = _gen_sales(rng, props)
    flipped = _plant_flips(rng, sales)
    private_props = _plant_private(rng, sales)

    mls_sales = [s for s in sales if not s["private"]]
    eligible = [i for i, s in enumerate(mls_sales) if not s["flip"]]
    n_conf = int(CONFLICT_RATE * len(mls_sales))
    price_conf = set(rng.choice(eligible, n_conf, replace=False))
    year_conf = set(rng.choice(eligible, n_conf, replace=False))

    mls_rows, price_conf_keys, year_conf_keys = [], [], []
    for i, s in enumerate(mls_sales):
        p = s["prop"]
        sold_price = s["price"]
        if i in price_conf:
            sold_price = _round500(s["price"] * (1 + float(rng.choice([-1, 1]))
                                                 * rng.uniform(0.013, 0.03)))
            price_conf_keys.append(normalize_address(p["civic"]))
        year = p["year_built"]
        if i in year_conf:
            delta = int(rng.choice([-1, 1])) * int(rng.integers(2, 6))
            year = p["year_built"] + delta
            if year > 2026:
                year = p["year_built"] - abs(delta)
            year_conf_keys.append(normalize_address(p["civic"]))
        mls_rows.append(dict(
            address=f"{p['civic']}, Calgary",
            beds=f"{p['beds']}+{p['beds_bsmt']}" if p["beds_bsmt"] else str(p["beds"]),
            baths=p["baths"], sqft=p["sqft"], garage_stalls=p["garage_stalls"],
            year_built=year,
            list_price=_round500(sold_price * rng.uniform(1.0, 1.05)),
            sold_price=sold_price, sold_date=s["sold_date"].isoformat()))

    lt_rows = [dict(
        legal_address=(f"PLAN {rng.integers(1000, 10000)} BLK {rng.integers(1, 21)} "
                       f"LOT {rng.integers(1, 100)}; {s['prop']['civic'].upper()}"),
        transfer_price=s["price"], transfer_date=s["sold_date"].isoformat())
        for s in sales]

    ass_rows = [dict(
        address=_assess_form(p["civic"]), community=p["community"],
        property_type=p["property_type"], lat=p["lat"], lon=p["lon"],
        year_built=p["year_built"], lot_sqft=p["lot_sqft"],
        assessed_value=p["assessed"]) for p in props]

    frames = {
        "mls_sales": pd.DataFrame(mls_rows, columns=[
            "address", "beds", "baths", "sqft", "garage_stalls", "year_built",
            "list_price", "sold_price", "sold_date"]),
        "land_titles": pd.DataFrame(lt_rows, columns=[
            "legal_address", "transfer_price", "transfer_date"]),
        "assessments": pd.DataFrame(ass_rows, columns=[
            "address", "community", "property_type", "lat", "lon", "year_built",
            "lot_sqft", "assessed_value"]),
    }
    manifest = dict(
        private=[normalize_address(p["civic"]) for p in private_props],
        flips=[normalize_address(p["civic"]) for p in flipped],
        price_conflicts=price_conf_keys,
        year_conflicts=year_conf_keys,
        stale_pocket=[normalize_address(p["civic"]) for p in props if p["pocket"]],
    )
    return World(frames=frames, manifest=manifest)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "raw")
    args = ap.parse_args()
    world = generate_world(seed=args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, df in world.frames.items():
        df.to_csv(args.out / f"{name}.csv", index=False)
        print(f"{name}.csv: {len(df)} rows")


if __name__ == "__main__":
    main()
