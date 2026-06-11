from datetime import date

import pytest

from data.merge import merge_sources
from data.schema import normalize_address
from data.sources import assessments, land_titles, mls

# Hand-written fixture (not generated data): six properties exercising every merge rule.
MLS_CSV = """\
address,beds,baths,sqft,garage_stalls,year_built,list_price,sold_price,sold_date
"123 Evanston Way NW, Calgary",3+1,2.5,1850,2,2021,635000,624000,2026-02-01
"#301, 880 12 Ave SW, Calgary",2,2.0,950,1,2012,405000,399000,2026-03-15
"10 Tuscany Ravine Rd NW, Calgary",4,3.0,2100,2,2005,602000,600000,2026-01-20
"55 Auburn Bay Blvd SE, Calgary",4,3.5,2200,2,2015,690000,688000,2026-04-02
"14 Evanston Dr NW, Calgary",3,2.5,1700,2,2018,560000,552000,2025-09-10
"14 Evanston Dr NW, Calgary",3,2.5,1700,2,2018,700000,690000,2026-01-15
"""

LAND_CSV = """\
legal_address,transfer_price,transfer_date
"PLAN 1111 BLK 1 LOT 1; 123 EVANSTON WAY NW",624000,2026-02-01
"PLAN 2222 BLK 2 LOT 2; #301, 880 12 AVE SW",399000,2026-03-15
"PLAN 3333 BLK 3 LOT 3; 10 TUSCANY RAVINE RD NW",612000,2026-01-20
"PLAN 4444 BLK 4 LOT 4; 55 AUBURN BAY BLVD SE",688000,2026-04-02
"PLAN 5555 BLK 5 LOT 5; 900 GLENBOW RD NW",310000,2025-12-05
"PLAN 6666 BLK 6 LOT 6; 14 EVANSTON DR NW",552000,2025-09-10
"PLAN 6666 BLK 6 LOT 6; 14 EVANSTON DR NW",690000,2026-01-15
"""

ASSESS_CSV = """\
address,community,property_type,lat,lon,year_built,lot_sqft,assessed_value
123 EVANSTON WY NW,Evanston,detached,51.1741,-114.1192,2021,4000,602000
UNIT 301 880 12 AV SW,Beltline,apartment,51.0421,-114.0716,2012,,388000
10 TUSCANY RAVINE RD NW,Tuscany,detached,51.1250,-114.2340,2005,4500,590000
55 AUBURN BAY BLVD SE,Auburn Bay,detached,50.8890,-113.9590,2012,4400,668000
900 GLENBOW RD NW,Bearspaw,detached,51.1860,-114.3700,2001,150000,1250000
14 EVANSTON DR NW,Evanston,detached,51.1735,-114.1185,2018,3800,640000
"""


@pytest.fixture(scope="module")
def merged(tmp_path_factory):
    raw = tmp_path_factory.mktemp("raw")
    (raw / "mls_sales.csv").write_text(MLS_CSV)
    (raw / "land_titles.csv").write_text(LAND_CSV)
    (raw / "assessments.csv").write_text(ASSESS_CSV)
    records = merge_sources(mls.load(raw / "mls_sales.csv"),
                            land_titles.load(raw / "land_titles.csv"),
                            assessments.load(raw / "assessments.csv"))
    return {r.address_key: r for r in records}


def _key(s: str) -> str:
    return normalize_address(s)


class TestMerge:
    def test_join_hits_across_all_three_address_formats(self, merged):
        # realtor, legal, and assessment formats all resolve to one record each
        for addr in ("123 Evanston Way NW", "#301, 880 12 Ave SW",
                     "10 Tuscany Ravine Rd NW", "55 Auburn Bay Blvd SE",
                     "900 Glenbow Rd NW", "14 Evanston Dr NW"):
            assert _key(addr) in merged, addr
        assert len(merged) == 6
        assert merged[_key("#301, 880 12 Ave SW")].community == "Beltline"

    def test_sources_map_every_populated_field_to_origin(self, merged):
        rec = merged[_key("123 Evanston Way NW")]
        assert rec.sources["sqft"] == "mls"
        assert rec.sources["beds"] == "mls"
        assert rec.sources["sold_price"] == "land_titles"
        assert rec.sources["sold_date"] == "land_titles"
        assert rec.sources["year_built"] == "assessment"
        assert rec.sources["lot_sqft"] == "assessment"
        assert rec.sources["assessed_value"] == "assessment"
        for field in ("community", "property_type", "beds", "baths", "sqft",
                      "year_built", "sold_price", "sold_date", "assessed_value"):
            assert getattr(rec, field) is not None
            assert field in rec.sources

    def test_price_precedence_land_titles_wins_and_conflict_recorded(self, merged):
        rec = merged[_key("10 Tuscany Ravine Rd NW")]
        assert rec.sold_price == 612_000  # land titles, not the MLS 600k
        [conflict] = [c for c in rec.conflicts if c.field == "sold_price"]
        assert conflict.resolved_with == "land_titles"
        assert conflict.values["mls"] == 600_000
        assert conflict.values["land_titles"] == 612_000

    def test_price_within_tolerance_records_no_conflict(self, merged):
        assert merged[_key("123 Evanston Way NW")].conflicts == []

    def test_year_built_precedence_assessment_wins(self, merged):
        rec = merged[_key("55 Auburn Bay Blvd SE")]
        assert rec.year_built == 2012  # assessment, not the MLS 2015
        [conflict] = [c for c in rec.conflicts if c.field == "year_built"]
        assert conflict.resolved_with == "assessment"
        assert conflict.values == {"mls": 2015, "assessment": 2012}

    def test_basement_beds_notation_split(self, merged):
        rec = merged[_key("123 Evanston Way NW")]
        assert rec.beds == 3
        assert rec.beds_bsmt == 1

    def test_private_sale_has_price_but_incomplete_for_comps(self, merged):
        rec = merged[_key("900 Glenbow Rd NW")]
        assert rec.sold_price == 310_000
        assert rec.sold_date == date(2025, 12, 5)
        assert rec.sources["sold_price"] == "land_titles"
        assert rec.sqft is None and rec.beds is None
        assert rec.complete_for_comps is False
        assert rec.assessed_value == 1_250_000  # still feeds non-arm's-length detection

    def test_full_record_is_complete_for_comps(self, merged):
        assert merged[_key("123 Evanston Way NW")].complete_for_comps is True

    def test_multiple_transfers_keep_latest_with_history(self, merged):
        rec = merged[_key("14 Evanston Dr NW")]
        assert rec.sold_price == 690_000
        assert rec.sold_date == date(2026, 1, 15)
        [history] = [c for c in rec.conflicts if c.resolved_with == "latest"]
        assert history.field == "sold_price"
        assert history.values["2025-09-10"] == 552_000
