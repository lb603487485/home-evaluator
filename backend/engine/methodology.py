"""Methodology text generated from engine/config.py + the risk-rule registry.

The single grounding artifact: S5 feeds it to /api/ask so chat answers about
method can't drift from code; S6 spends it again as UI popovers and a handbook.
Pure — no LLM imports."""

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
