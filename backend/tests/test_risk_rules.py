from datetime import date

from data.schema import Conflict, PropertyRecord, SubjectProperty
from engine.risk_rules import RISK_RULES, RiskFlag, ValuationContext, evaluate_rules
from engine.scoring import score_comps
from engine.valuation import valuate

TODAY = date(2026, 6, 1)
CENTER = (51.1740, -114.1190)

SUBJECT = SubjectProperty(community="Evanston", property_type="detached", beds=3,
                          baths=2.5, sqft=1850, year_built=2020, lot_sqft=4000,
                          garage_stalls=2)


def rec(key, price=600_000, **kw):
    base = dict(address_key=key, address=key, community="Evanston",
                property_type="detached", beds=3, baths=2.5, sqft=1850,
                lot_sqft=4000, year_built=2020, garage_stalls=2,
                lat=CENTER[0], lon=CENTER[1], sold_price=price,
                sold_date=TODAY, assessed_value=600_000)
    return PropertyRecord(**(base | kw))


def context(records=None, subject=SUBJECT, **kw):
    records = records if records is not None else [
        rec(f"c{i}", p) for i, p in enumerate([600_000, 602_000, 598_000,
                                               601_000, 599_000, 600_500])]
    scored = score_comps(records, subject, CENTER, TODAY)
    return ValuationContext(subject=subject, scored=scored,
                            valuation=valuate(scored, subject, TODAY),
                            today=TODAY, **kw)


def codes(ctx):
    return {f.code for f in evaluate_rules(ctx)}


class TestRiskRules:
    def test_clean_context_raises_no_flags(self):
        assert codes(context()) == set()

    def test_thin_comps(self):
        ctx = context([rec("a"), rec("b"), rec("c")])
        assert "THIN_COMPS" in codes(ctx)

    def test_high_dispersion(self):
        spread = [rec(f"s{i}", p) for i, p in
                  enumerate(range(500_000, 720_000, 40_000))]
        assert "HIGH_DISPERSION" in codes(context(spread))

    def test_non_arms_length_excluded(self):
        ctx = context(exclusions=[dict(address_key="x", reason="non_arms_length",
                                       ratio=0.55)])
        assert "NON_ARMS_LENGTH_EXCLUDED" in codes(ctx)
        other = context(exclusions=[dict(address_key="x", reason="incomplete")])
        assert "NON_ARMS_LENGTH_EXCLUDED" not in codes(other)

    def test_data_conflict_on_source_disagreement_only(self):
        conflicted = rec("c0", conflicts=[Conflict(
            field="sold_price", values={"mls": 600_000, "land_titles": 612_000},
            resolved_with="land_titles")])
        history = rec("c1", conflicts=[Conflict(
            field="sold_price", values={"2025-09-10": 552_000}, resolved_with="latest")])
        five = [rec(f"f{i}") for i in range(5)]
        assert "DATA_CONFLICT" in codes(context([conflicted] + five))
        assert "DATA_CONFLICT" not in codes(context([history] + five))

    def test_extrapolation_when_subject_outside_comp_range(self):
        big_subject = SUBJECT.model_copy(update={"sqft": 2500})
        assert "EXTRAPOLATION" in codes(context(subject=big_subject))

    def test_stale_comps(self):
        stale = [rec(f"s{i}", sold_date=date(2025, 11, 1)) for i in range(6)]
        assert "STALE_COMPS" in codes(context(stale))

    def test_widened_search(self):
        log = [dict(round=0, found=2, reason="initial"),
               dict(round=1, found=7, reason="extend_days: thin")]
        assert "WIDENED_SEARCH" in codes(context(search_log=log))
        assert "WIDENED_SEARCH" not in codes(
            context(search_log=[dict(round=0, found=9, reason="initial")]))

    def test_registry_appended_rule_is_evaluated(self):
        rule = lambda ctx: RiskFlag(code="CUSTOM", severity="info", message="x")
        RISK_RULES.append(rule)
        try:
            assert "CUSTOM" in codes(context())
        finally:
            RISK_RULES.remove(rule)
