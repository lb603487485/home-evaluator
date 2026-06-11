from datetime import date

import pytest

from data.schema import PropertyRecord, SubjectProperty
from engine.scoring import score_comps
from engine.valuation import valuate

TODAY = date(2026, 6, 1)
CENTER = (51.1740, -114.1190)

SUBJECT = SubjectProperty(community="Evanston", property_type="detached", beds=3,
                          baths=2.5, sqft=1850, year_built=2020, lot_sqft=4000,
                          garage_stalls=2)


def rec(key, price, **kw):
    base = dict(address_key=key, address=key, community="Evanston",
                property_type="detached", beds=3, baths=2.5, sqft=1850,
                lot_sqft=4000, year_built=2020, garage_stalls=2,
                lat=CENTER[0], lon=CENTER[1], sold_price=price,
                sold_date=TODAY, assessed_value=600_000)
    return PropertyRecord(**(base | kw))


def valuation_of(records):
    return valuate(score_comps(records, SUBJECT, CENTER, TODAY), SUBJECT, TODAY)


# Hand-computed fixture: subject twin + one deviation per comp.
#   c1 twin 600,000 → 600,000
#   c2 sqft 2050 @ ppsf 300 → sqft adj (1850-2050)*0.5*300 = -30,000 → 585,000
#   c3 2 beds → +8,000 → 588,000
#   c4 3.5 baths (-6,000), 3 garage (-10,000) → 594,000
#   c5 built 2010 → +10*800 = +8,000 → 596,000
#   c6 sold 365d ago (4 quarters @1.2%) → 570,000*(1.012^4-1) ≈ +27,856 → 597,856
FIXTURE = [
    rec("c1", 600_000),
    rec("c2", 615_000, sqft=2050),
    rec("c3", 580_000, beds=2),
    rec("c4", 610_000, baths=3.5, garage_stalls=3),
    rec("c5", 588_000, year_built=2010),
    rec("c6", 570_000, sold_date=date(2025, 6, 1)),
]


class TestAdjustments:
    def test_each_comp_adjusts_to_hand_computed_value(self):
        val = valuation_of(FIXTURE)
        adjusted = {a.address_key: a.adjusted_price for a in val.adjustments}
        assert adjusted["c1"] == 600_000
        assert adjusted["c2"] == 585_000
        assert adjusted["c3"] == 588_000
        assert adjusted["c4"] == 594_000
        assert adjusted["c5"] == 596_000
        assert adjusted["c6"] == pytest.approx(597_856, abs=1)

    def test_time_adjustment_uses_community_trend_index(self):
        val = valuation_of([rec("stale", 570_000, sold_date=date(2025, 6, 1))])
        [a] = val.adjustments
        assert a.adjustments["time"] == pytest.approx(570_000 * (1.012**4 - 1), rel=1e-6)

    def test_direction_bigger_comp_adjusts_down(self):
        val = valuation_of([rec("big", 615_000, sqft=2050)])
        assert val.adjustments[0].adjustments["sqft"] < 0

    def test_direction_fewer_beds_adjusts_up(self):
        val = valuation_of([rec("fewer", 580_000, beds=2)])
        assert val.adjustments[0].adjustments["beds"] == 8_000

    def test_direction_more_baths_adjusts_down(self):
        val = valuation_of([rec("baths", 610_000, baths=3.5)])
        assert val.adjustments[0].adjustments["baths"] == -6_000

    def test_direction_fewer_garage_adjusts_up(self):
        val = valuation_of([rec("garage", 600_000, garage_stalls=1)])
        assert val.adjustments[0].adjustments["garage"] == 10_000

    def test_direction_newer_comp_adjusts_down(self):
        val = valuation_of([rec("newer", 620_000, year_built=2024)])
        assert val.adjustments[0].adjustments["age"] == -3_200

    def test_age_adjustment_capped(self):
        val = valuation_of([rec("old", 500_000, year_built=1980)])
        assert val.adjustments[0].adjustments["age"] == 20_000

    def test_lot_deadband_then_rate(self):
        within = valuation_of([rec("within", 600_000, lot_sqft=5000)])
        beyond = valuation_of([rec("beyond", 600_000, lot_sqft=7000)])
        assert within.adjustments[0].adjustments["lot"] == 0
        assert beyond.adjustments[0].adjustments["lot"] == -2_000  # (3000-2000)*2.0 down


class TestEstimate:
    def test_weighted_median_and_range(self):
        val = valuation_of(FIXTURE)
        assert val.estimate == 594_000  # weighted median lands on c4
        assert val.low == 588_000       # weighted P25 on c3
        assert val.high == pytest.approx(597_856, abs=1)  # weighted P75 on c6

    def test_confidence_a_on_fixture(self):
        assert valuation_of(FIXTURE).confidence == "A"

    def test_confidence_c_on_three_comps(self):
        assert valuation_of(FIXTURE[:3]).confidence == "C"

    def test_confidence_not_a_when_dispersed(self):
        spread = [rec(f"s{i}", price) for i, price in
                  enumerate(range(500_000, 720_000, 40_000))]
        assert valuation_of(spread).confidence != "A"
