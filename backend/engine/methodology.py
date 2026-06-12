"""Methodology generated from engine/config.py + the risk-rule registry.

The single grounding artifact, spent three ways so none can drift from code:
S5 feeds the text block to /api/ask (chat grounding) · S6 serves the structured
form to UI popovers (GET /api/methodology) and renders docs/handbook.md
(regenerate: `uv run python -m engine.methodology`; a test pins the file to
this generator). Pure — no LLM imports."""

from engine import config

# Keys must match the registry-derived codes (rule.__name__) — enforced by test.
RISK_RULE_MEANINGS = {
    "THIN_COMPS": f"fewer than {config.MIN_COMPS} comparable sales support the "
                  "estimate",
    "HIGH_DISPERSION": "adjusted comp prices spread "
                       f"≥{config.CONFIDENCE['C']['min_iqr']:.0%} of the estimate — "
                       "volatile market for this profile",
    "NON_ARMS_LENGTH_EXCLUDED": "excluded suspected non-open-market transfer(s): "
                                f"sold below {config.NON_ARMS_LENGTH_RATIO:.0%} of "
                                "assessed value",
    "DATA_CONFLICT": "sources disagreed on a comp's values beyond "
                     f"{config.PRICE_CONFLICT_TOL:.1%}; documented precedence "
                     "applied, conflict recorded",
    "EXTRAPOLATION": "subject size falls outside the comp set's observed range",
    "STALE_COMPS": f"median comp sale is older than {config.STALE_DAYS} days; time "
                   "adjustments carry more of the estimate",
    "WIDENED_SEARCH": "search criteria were widened to find enough comps; the "
                      "agent's reasons are logged per round",
    "BASELINE_DIVERGENCE": "estimate differs more than "
                           f"{config.BASELINE_TOLERANCE:.0%} from the market-norm "
                           "baseline (median $/sqft × subject size; silent under "
                           f"{config.BASELINE_MIN_SAMPLE} sales)",
}


def methodology_block() -> str:
    weights = " · ".join(f"{dim} {w}" for dim, w in config.WEIGHTS.items())
    f, w, adj = config.FILTER_DEFAULTS, config.WIDENING_MOVES, config.ADJ
    a, c = config.CONFIDENCE["A"], config.CONFIDENCE["C"]
    trend = " · ".join(f"{name} {rate:.1%}/quarter"
                       for name, rate in config.MARKET_TREND_QOQ.items())
    rules = "\n".join(f"- {code}: {meaning}"
                      for code, meaning in RISK_RULE_MEANINGS.items())
    return f"""\
SIMILARITY (0–100, weighted sum): {weights}.
Each dimension scores full points at zero difference and falls linearly to zero at its
normalizer (e.g. recency reaches zero at {config.SCORE_NORM['recency_days']:.0f} days; old sale prices are also
time-corrected — see ADJUSTMENTS — so recency covers what correction can't fix).

SEARCH: same community + property type, radius {f['radius_km']} km, last {f['days']} days, sqft ±{f['sqft_pct']:.0%},
beds ±{f['beds_delta']}. Under {config.MIN_COMPS} comps the agent may widen ≤{config.MAX_WIDEN_ROUNDS} rounds, choosing among:
+{w['extend_days'][0]} days (cap {w['extend_days'][1]}) · radius ×{w['widen_radius'][0]} (cap {w['widen_radius'][1]} km) · sqft to ±{w['relax_sqft'][0]:.0%} · beds to ±{w['relax_beds'][0]}.
Top {config.TOP_N_REVIEW} comps go to individual review; demoted comps count at half weight.

ADJUSTMENTS (dollars toward the subject, per comp): time = community quarterly trend
compounded since the sale date · sqft = {adj['ppsf_marginal']:.0%} of the comp's own $/sqft × size gap ·
beds ${adj['bed']:,} each · baths ${adj['bath']:,} · garage stalls ${adj['garage']:,} · age ${adj['age_per_year']:,}/yr capped
at ${adj['age_cap']:,} · lot ${adj['lot_per_sqft']:g}/sqft beyond a {adj['lot_deadband']:,} sqft deadband.
Quarterly trend rates: {trend}.

VALUATION: similarity-weighted median of adjusted prices; range = weighted P25–P75.

CONFIDENCE: A = ≥{a['min_comps']} comps, spread ≤{a['max_iqr']:.0%} of estimate, mean similarity ≥{a['min_sim']} ·
C = ≤{c['max_comps']} comps or spread ≥{c['min_iqr']:.0%} · B = otherwise.

RISK FLAGS:
{rules}"""


def confidence_meanings() -> dict[str, str]:
    a, c = config.CONFIDENCE["A"], config.CONFIDENCE["C"]
    return {
        "A": f"strong evidence: ≥{a['min_comps']} comps, adjusted-price spread "
             f"≤{a['max_iqr']:.0%} of the estimate, mean similarity ≥{a['min_sim']}",
        "B": "usable evidence — between the A and C criteria",
        "C": f"weak evidence: ≤{c['max_comps']} comps, or spread "
             f"≥{c['min_iqr']:.0%} of the estimate",
    }


def methodology_data() -> dict:
    """Structured form for the UI popovers — same constants, same meanings."""
    return {
        "weights": dict(config.WEIGHTS),
        "confidence": confidence_meanings(),
        "flags": dict(RISK_RULE_MEANINGS),
    }


def handbook_markdown() -> str:
    f, w, adj = config.FILTER_DEFAULTS, config.WIDENING_MOVES, config.ADJ
    weights = "\n".join(f"| {dim} | {weight} | falls linearly to 0 at "
                        f"{_norm_label(dim)} |"
                        for dim, weight in config.WEIGHTS.items())
    trend = "\n".join(f"| {name} | {rate:.1%}/quarter |"
                      for name, rate in config.MARKET_TREND_QOQ.items())
    grades = "\n".join(f"| {grade} | {meaning} |"
                       for grade, meaning in confidence_meanings().items())
    flags = "\n".join(f"| `{code}` | {meaning} |"
                      for code, meaning in RISK_RULE_MEANINGS.items())
    return f"""\
# Methodology handbook

Generated from `backend/engine/config.py` and the risk-rule registry —
**do not edit by hand**. Regenerate: `uv run python -m engine.methodology`
(a test pins this file to the generator, so a config change without
regeneration fails CI).

## Similarity scoring (0–100, weighted sum)

| dimension | weight | decay |
|---|---|---|
{weights}

Same-community is all-or-nothing; a lot-less pair (e.g. two apartments) scores
lot as fully comparable. Old sale *prices* are separately corrected forward
(see Adjustments) — recency covers only what correction can't fix.

## Search & widening

Initial filters: same community + property type · radius {f['radius_km']} km · last {f['days']} days ·
sqft ±{f['sqft_pct']:.0%} · beds ±{f['beds_delta']}. Under {config.MIN_COMPS} comps the agent may widen ≤{config.MAX_WIDEN_ROUNDS} rounds,
choosing one move per round from engine-projected counts: +{w['extend_days'][0]} days (cap {w['extend_days'][1]}) ·
radius ×{w['widen_radius'][0]} (cap {w['widen_radius'][1]} km) · sqft to ±{w['relax_sqft'][0]:.0%} · beds to ±{w['relax_beds'][0]}. Top {config.TOP_N_REVIEW} comps go to
individual review; demoted comps count at half weight.

## Adjustments (dollars toward the subject, per comp)

- **time** — community quarterly trend, compounded since the sale date
- **sqft** — {adj['ppsf_marginal']:.0%} of the comp's own $/sqft × size gap
- **beds** ${adj['bed']:,} each · **baths** ${adj['bath']:,} · **garage stalls** ${adj['garage']:,}
- **age** — ${adj['age_per_year']:,}/yr, capped at ${adj['age_cap']:,}
- **lot** — ${adj['lot_per_sqft']:g}/sqft beyond a {adj['lot_deadband']:,} sqft deadband

| community | trend |
|---|---|
{trend}

## Valuation & confidence

Estimate = similarity-weighted **median** of adjusted prices; range = weighted
P25–P75.

| grade | meaning |
|---|---|
{grades}

## Risk flags

| flag | meaning |
|---|---|
{flags}
"""


def _norm_label(dim: str) -> str:
    n = config.SCORE_NORM
    labels = {
        "distance": f"{n['distance_km']:g} km",
        "recency": f"{n['recency_days']:.0f} days",
        "sqft": f"±{n['sqft_band_pct']:.0%} of subject size",
        "beds_baths": f"a combined delta of {n['beds_baths']:g}",
        "year_built": f"{n['year_years']:g} years",
        "lot": f"{n['lot_sqft']:,.0f} sqft difference",
        "garage": f"{n['garage_stalls']:g} stalls",
        "same_community": "n/a (all-or-nothing)",
    }
    return labels[dim]


if __name__ == "__main__":
    from pathlib import Path
    out = Path(__file__).resolve().parent.parent.parent / "docs" / "handbook.md"
    out.write_text(handbook_markdown())
    print(f"→ {out}")
