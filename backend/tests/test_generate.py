from datetime import date, timedelta

import numpy as np
import pytest

from data.generate import generate_world
from data.price_model import TREND_ANCHOR, true_price
from data.schema import normalize_address

FIXTURE = dict(community="Evanston", property_type="detached", sqft=1850,
               beds=3, baths=2.5, year_built=2021, garage_stalls=2)

# spec §3 volumes table (sales per community over 24 months)
SALES_TARGETS = {"Beltline": 500, "Bridgeland": 300, "Killarney": 350,
                 "Tuscany": 450, "Evanston": 500, "Auburn Bay": 400,
                 "Aspen Woods": 150, "Bearspaw": 5}


class TestPriceModel:
    def test_fixture_lands_in_plausible_range(self):
        assert 580_000 <= true_price(FIXTURE, date(2026, 2, 1)) <= 660_000

    def test_newer_sale_prices_higher_than_older(self):
        older = true_price(FIXTURE, date(2025, 3, 1))
        newer = true_price(FIXTURE, date(2026, 3, 1))
        assert newer > older


@pytest.fixture(scope="module")
def world():
    return generate_world(seed=42)


def _civic_key(legal_address: str) -> str:
    return normalize_address(legal_address.split(";")[1])


def _community_map(world) -> dict[str, str]:
    ass = world.frames["assessments"]
    return {normalize_address(a): c for a, c in zip(ass["address"], ass["community"])}


class TestGenerator:
    def test_sales_volumes_within_20pct_of_spec(self, world):
        communities = _community_map(world)
        lt = world.frames["land_titles"]
        counts: dict[str, int] = {}
        for legal in lt["legal_address"]:
            c = communities[_civic_key(legal)]
            counts[c] = counts.get(c, 0) + 1
        for community, target in SALES_TARGETS.items():
            assert abs(counts[community] - target) <= 0.2 * target + 2, community

    def test_bearspaw_is_thin(self, world):
        communities = _community_map(world)
        lt = world.frames["land_titles"]
        n = sum(communities[_civic_key(a)] == "Bearspaw" for a in lt["legal_address"])
        assert n == 5

    def test_deterministic_for_same_seed(self, world):
        again = generate_world(seed=42)
        for name, frame in world.frames.items():
            assert frame.equals(again.frames[name]), name
        assert world.manifest == again.manifest

    def test_private_sales_planted_below_assessed_ratio(self, world):
        keys = world.manifest["private"]
        assert len(keys) >= 10
        mls_keys = {normalize_address(a) for a in world.frames["mls_sales"]["address"]}
        ass = world.frames["assessments"]
        assessed = {normalize_address(a): v
                    for a, v in zip(ass["address"], ass["assessed_value"])}
        lt = world.frames["land_titles"]
        price = {_civic_key(a): p for a, p in zip(lt["legal_address"], lt["transfer_price"])}
        for key in keys:
            assert key not in mls_keys  # no MLS record for private sales
            assert price[key] / assessed[key] < 0.75

    def test_two_flips_planted(self, world):
        keys = world.manifest["flips"]
        assert len(keys) == 2
        lt = world.frames["land_titles"]
        for key in keys:
            rows = [(date.fromisoformat(d), p) for a, d, p in
                    zip(lt["legal_address"], lt["transfer_date"], lt["transfer_price"])
                    if _civic_key(a) == key]
            assert len(rows) == 2
            rows.sort()
            (d1, p1), (d2, p2) = rows
            assert d2 - d1 < timedelta(days=183)
            assert p2 == pytest.approx(p1 * 1.25, rel=0.01)

    def test_price_conflicts_planted(self, world):
        keys = world.manifest["price_conflicts"]
        assert len(keys) >= 20
        mls = world.frames["mls_sales"]
        mls_price = {normalize_address(a): p for a, p in zip(mls["address"], mls["sold_price"])}
        lt = world.frames["land_titles"]
        lt_price = {_civic_key(a): p for a, p in zip(lt["legal_address"], lt["transfer_price"])}
        for key in keys[:20]:
            delta = abs(mls_price[key] - lt_price[key]) / lt_price[key]
            assert 0.008 <= delta <= 0.035

    def test_year_built_conflicts_planted(self, world):
        keys = world.manifest["year_conflicts"]
        assert len(keys) >= 20
        mls = world.frames["mls_sales"]
        mls_year = {normalize_address(a): y for a, y in zip(mls["address"], mls["year_built"])}
        ass = world.frames["assessments"]
        true_year = {normalize_address(a): y for a, y in zip(ass["address"], ass["year_built"])}
        for key in keys[:20]:
            assert 2 <= abs(mls_year[key] - true_year[key]) <= 5

    def test_stale_tuscany_pocket(self, world):
        keys = set(world.manifest["stale_pocket"])
        assert len(keys) >= 10
        communities = _community_map(world)
        assert all(communities[k] == "Tuscany" for k in keys)
        lt = world.frames["land_titles"]
        pocket_dates = [date.fromisoformat(d) for a, d in
                        zip(lt["legal_address"], lt["transfer_date"])
                        if _civic_key(a) in keys]
        assert len(pocket_dates) >= 5  # enough comps to find, all stale
        assert all(d <= TREND_ANCHOR - timedelta(days=120) for d in pocket_dates)

    def test_aspen_woods_noisier_than_evanston(self, world):
        skip = set(world.manifest["price_conflicts"]) | set(world.manifest["flips"])
        ass = world.frames["assessments"]
        attrs_by_key = {
            normalize_address(a): dict(community=c, property_type=t,
                                       lot_sqft=lot if lot == lot else None,
                                       year_built=y)
            for a, c, t, lot, y in zip(ass["address"], ass["community"],
                                       ass["property_type"], ass["lot_sqft"],
                                       ass["year_built"])
        }

        def ratio_sd(community: str) -> float:
            mls = world.frames["mls_sales"]
            ratios = []
            for a, beds, baths, sqft, gar, price, sold in zip(
                    mls["address"], mls["beds"], mls["baths"], mls["sqft"],
                    mls["garage_stalls"], mls["sold_price"], mls["sold_date"]):
                key = normalize_address(a)
                base = attrs_by_key[key]
                if base["community"] != community or key in skip:
                    continue
                above, _, bsmt = str(beds).partition("+")
                attrs = base | dict(beds=int(above), beds_bsmt=int(bsmt or 0),
                                    baths=float(baths), sqft=int(sqft),
                                    garage_stalls=int(gar))
                ratios.append(price / true_price(attrs, date.fromisoformat(sold)))
            return float(np.std(ratios))

        assert ratio_sd("Aspen Woods") > 1.5 * ratio_sd("Evanston")
