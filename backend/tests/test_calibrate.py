"""The calibration fit must run on the shipped parquet and recover the
generator's linear structure — the mechanism demo behind the ML roadmap."""

from eval.calibrate import fit, load_frame, render


def test_fit_recovers_generator_structure():
    res = fit(load_frame())
    assert res["n"] > 2_000
    assert res["r2"] > 0.9
    f = res["fitted"]
    assert 6_000 < f["beds"] < 10_000        # config bed = 8,000
    assert 8_000 < f["garage"] < 14_000      # config garage = 10,000
    assert 1.0 < f["lot_sqft"] < 3.0         # config lot_per_sqft = 2.0
    assert f["days_ago"] < 0                 # older sales cheaper (positive trend)


def test_render_mentions_every_engine_rate():
    md = render(fit(load_frame()))
    for term in ("bedroom", "bathroom", "garage", "age", "lot", "market trend"):
        assert term in md
