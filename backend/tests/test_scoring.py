from datetime import date

import pytest

from data.schema import PropertyRecord, SubjectProperty
from engine.config import WEIGHTS
from engine.scoring import score_comps

TODAY = date(2026, 6, 1)
CENTER = (51.1740, -114.1190)

SUBJECT = SubjectProperty(community="Evanston", property_type="detached", beds=3,
                          baths=2.5, sqft=1850, year_built=2020, lot_sqft=4000,
                          garage_stalls=2)


def rec(key, **kw):
    base = dict(address_key=key, address=key, community="Evanston",
                property_type="detached", beds=3, baths=2.5, sqft=1850,
                lot_sqft=4000, year_built=2020, garage_stalls=2,
                lat=CENTER[0], lon=CENTER[1], sold_price=620_000,
                sold_date=TODAY, assessed_value=600_000)
    return PropertyRecord(**(base | kw))


def score_of(record):
    [scored] = score_comps([record], SUBJECT, CENTER, TODAY)
    return scored


class TestScoring:
    def test_weights_sum_to_100(self):
        assert sum(WEIGHTS.values()) == 100

    def test_identical_twin_scores_100(self):
        assert score_of(rec("twin")).score == pytest.approx(100, abs=0.5)

    def test_score_equals_sum_of_parts_with_all_dimensions(self):
        scored = score_of(rec("twin", sqft=2000, lat=CENTER[0] + 0.01))
        assert set(scored.score_parts) == set(WEIGHTS)
        assert scored.score == pytest.approx(sum(scored.score_parts.values()), abs=0.01)

    def test_monotonic_distance(self):
        nearer = score_of(rec("a", lat=CENTER[0] + 0.009))   # ~1 km
        farther = score_of(rec("b", lat=CENTER[0] + 0.027))  # ~3 km
        assert farther.score < nearer.score

    def test_monotonic_recency(self):
        fresh = score_of(rec("a", sold_date=date(2026, 5, 2)))   # 30 days back
        stale = score_of(rec("b", sold_date=date(2025, 11, 13)))  # 200 days back
        assert stale.score < fresh.score

    def test_monotonic_sqft_difference(self):
        same = score_of(rec("a"))
        bigger = score_of(rec("b", sqft=2150))
        assert bigger.score < same.score

    def test_sorted_descending(self):
        scored = score_comps([rec("far", lat=CENTER[0] + 0.027), rec("twin")],
                             SUBJECT, CENTER, TODAY)
        assert [s.comp.address_key for s in scored] == ["twin", "far"]
