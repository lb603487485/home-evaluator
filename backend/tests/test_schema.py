from datetime import date

from data.schema import PropertyRecord, SubjectProperty, normalize_address


class TestNormalizeAddress:
    def test_realtor_format_matches_bare_uppercase(self):
        assert normalize_address("123 Evanston Way NW, Calgary") == normalize_address(
            "123 EVANSTON WAY NW"
        )

    def test_unit_prefix_hash_matches_unit_keyword(self):
        assert normalize_address("#301, 880 12 Ave SW") == normalize_address(
            "UNIT 301 880 12 AVENUE SW"
        )

    def test_apt_prefix_matches_hash(self):
        assert normalize_address("APT 12 700 9 Street SW") == normalize_address(
            "#12, 700 9 ST SW"
        )

    def test_suffix_abbreviations(self):
        assert normalize_address("456 Tuscany Avenue Northwest") == normalize_address(
            "456 TUSCANY AVE NW"
        )

    def test_assessment_wy_matches_way(self):
        assert normalize_address("123 EVANSTON WY NW") == normalize_address(
            "123 Evanston Way NW"
        )

    def test_punctuation_and_case_stripped(self):
        assert normalize_address("123 Auburn Bay Blvd. SE,") == normalize_address(
            "123 auburn bay blvd se"
        )

    def test_city_dropped(self):
        assert normalize_address("77 Killarney St SW, Calgary") == normalize_address(
            "77 Killarney St SW"
        )


class TestPropertyRecord:
    def test_round_trip_with_empty_defaults(self):
        rec = PropertyRecord(
            address_key="123 EVANSTON WAY NW",
            address="123 Evanston Way NW",
            community="Evanston",
            property_type="detached",
            beds=3,
            baths=2.5,
            sqft=1850,
            lot_sqft=4200,
            year_built=2021,
            garage_stalls=2,
            lat=51.17,
            lon=-114.12,
            sold_price=625_000,
            sold_date=date(2026, 2, 14),
            assessed_value=598_000,
        )
        assert rec.sources == {}
        assert rec.conflicts == []
        assert rec.beds_bsmt == 0
        assert PropertyRecord.model_validate_json(rec.model_dump_json()) == rec


def test_subject_address_optional_passthrough():
    s = SubjectProperty(community="Evanston", property_type="detached", beds=3,
                        baths=2.5, sqft=1850, year_built=2020)
    assert s.address == ""
    s2 = s.model_copy(update={"address": "310 Evanston Dr NW"})
    assert "310 Evanston Dr NW" in s2.model_dump_json()
