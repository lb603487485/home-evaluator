"""S10: eval.feedback report — deterministic diagnosis over the feedback log.
Feedback proposes, eval disposes; the report only localizes and names knobs."""


def _line(rating, estimate, user_estimate, confidence="B",
          community="Evanston", flags=()):
    return {"session_id": "s", "rating": rating, "comment": "",
            "user_estimate": user_estimate,
            "snapshot": {"subject": {"community": community},
                         "estimate": estimate, "confidence": confidence,
                         "flags": list(flags), "comps": []}}


def test_report_empty_log_is_graceful():
    from eval.feedback import build_report
    assert "no feedback" in build_report([]).lower()


def test_report_shows_n_and_small_sample_caveat():
    from eval.feedback import build_report
    report = build_report([_line(4, 700_000, 720_000)])
    assert "n=1" in report
    assert "directional only" in report


def test_report_slices_user_vs_engine_delta_by_confidence():
    from eval.feedback import build_report
    report = build_report([_line(3, 700_000, 770_000, confidence="C"),
                           _line(4, 700_000, 700_000, confidence="A")])
    assert "confidence C" in report
    assert "+10.0%" in report  # (770k-700k)/700k, sliced to the C run


def test_report_callout_names_config_knob():
    from eval.feedback import build_report
    report = build_report([_line(2, 700_000, 770_000, confidence="C"),
                           _line(3, 600_000, 680_000, confidence="C")])
    assert "config.py" in report  # consistent C-slice gap → named knob


def test_report_no_callout_under_threshold():
    from eval.feedback import build_report
    report = build_report([_line(4, 700_000, 707_000),
                           _line(4, 700_000, 693_000)])
    assert "investigate" not in report


def test_report_mean_rating():
    from eval.feedback import build_report
    report = build_report([_line(2, 700_000, None), _line(4, 700_000, None)])
    assert "3.0" in report  # mean rating over all records
