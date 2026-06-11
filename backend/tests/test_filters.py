from datetime import date

from engine.filters import SearchCriteria, apply_filters, apply_move, records_frame
from data.schema import PropertyRecord, SubjectProperty

TODAY = date(2026, 6, 1)
CENTER = (51.1740, -114.1190)  # Evanston

SUBJECT = SubjectProperty(community="Evanston", property_type="detached", beds=3,
                          baths=2.5, sqft=1850, year_built=2020, lot_sqft=4000,
                          garage_stalls=2)


def rec(key, **kw):
    base = dict(address_key=key, address=key, community="Evanston",
                property_type="detached", beds=3, baths=2.5, sqft=1850,
                lot_sqft=4000, year_built=2020, garage_stalls=2,
                lat=CENTER[0], lon=CENTER[1], sold_price=620_000,
                sold_date=date(2026, 5, 1), assessed_value=600_000)
    return PropertyRecord(**(base | kw))


def keys_after(records, criteria=SearchCriteria()):
    df = apply_filters(records_frame(records), SUBJECT, CENTER, criteria, TODAY)
    return set(df["address_key"])


class TestFilters:
    def test_property_type_must_match(self):
        assert keys_after([rec("ok"), rec("town", property_type="townhouse")]) == {"ok"}

    def test_haversine_radius(self):
        far = rec("far", lat=CENTER[0] + 0.05)  # ~5.6 km north
        near = rec("near", lat=CENTER[0] + 0.01)  # ~1.1 km
        assert keys_after([near, far]) == {"near"}
        assert keys_after([near, far], SearchCriteria(radius_km=10)) == {"near", "far"}

    def test_days_window(self):
        stale = rec("stale", sold_date=date(2025, 9, 1))  # 273 days back
        assert keys_after([rec("recent"), stale]) == {"recent"}
        assert keys_after([stale], SearchCriteria(days=365)) == {"stale"}

    def test_sqft_band(self):
        assert keys_after([rec("close", sqft=2300), rec("huge", sqft=2400)]) == {"close"}

    def test_beds_delta(self):
        assert keys_after([rec("four", beds=4), rec("six", beds=6)]) == {"four"}

    def test_incomplete_records_excluded(self):
        private = rec("private", beds=None, baths=None, sqft=None)
        assert keys_after([rec("ok"), private]) == {"ok"}


class TestWidening:
    def test_extend_days_respects_cap(self):
        c = SearchCriteria()
        for _ in range(5):
            c = apply_move(c, "extend_days")
        assert c.days == 365

    def test_widen_radius_respects_cap(self):
        c = SearchCriteria()
        for _ in range(5):
            c = apply_move(c, "widen_radius")
        assert c.radius_km == 5.0

    def test_relax_sqft_and_beds(self):
        c = apply_move(apply_move(SearchCriteria(), "relax_sqft"), "relax_beds")
        assert c.sqft_pct == 0.35
        assert c.beds_delta == 2

    def test_apply_move_is_pure(self):
        original = SearchCriteria()
        widened = apply_move(original, "widen_radius")
        assert original.radius_km == SearchCriteria().radius_km
        assert widened is not original
        assert widened.radius_km > original.radius_km
