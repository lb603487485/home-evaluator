# Methodology handbook

Generated from `backend/engine/config.py` and the risk-rule registry —
**do not edit by hand**. Regenerate: `uv run python -m engine.methodology`
(a test pins this file to the generator, so a config change without
regeneration fails CI).

## Similarity scoring (0–100, weighted sum)

| dimension | weight | decay |
|---|---|---|
| distance | 25 | falls linearly to 0 at 5 km |
| recency | 20 | falls linearly to 0 at 365 days |
| sqft | 20 | falls linearly to 0 at ±35% of subject size |
| beds_baths | 10 | falls linearly to 0 at a combined delta of 4 |
| year_built | 10 | falls linearly to 0 at 30 years |
| lot | 5 | falls linearly to 0 at 10,000 sqft difference |
| garage | 5 | falls linearly to 0 at 2 stalls |
| same_community | 5 | falls linearly to 0 at n/a (all-or-nothing) |

Same-community is all-or-nothing; a lot-less pair (e.g. two apartments) scores
lot as fully comparable. Old sale *prices* are separately corrected forward
(see Adjustments) — recency covers only what correction can't fix.

## Search & widening

Initial filters: same community + property type · radius 2.0 km · last 180 days ·
sqft ±25% · beds ±1. Under 5 comps the agent may widen ≤2 rounds,
choosing one move per round from engine-projected counts: +90 days (cap 365) ·
radius ×1.5 (cap 5.0 km) · sqft to ±35% · beds to ±2. Top 8 comps go to
individual review; demoted comps count at half weight.

## Adjustments (dollars toward the subject, per comp)

- **time** — community quarterly trend, compounded since the sale date
- **sqft** — 50% of the comp's own $/sqft × size gap
- **beds** $8,000 each · **baths** $6,000 · **garage stalls** $10,000
- **age** — $800/yr, capped at $20,000
- **lot** — $2/sqft beyond a 2,000 sqft deadband

| community | trend |
|---|---|
| Beltline | 1.8%/quarter |
| Bridgeland | 1.2%/quarter |
| Killarney | 1.2%/quarter |
| Tuscany | 1.2%/quarter |
| Evanston | 1.2%/quarter |
| Auburn Bay | 1.2%/quarter |
| Aspen Woods | 1.2%/quarter |
| Bearspaw | 0.6%/quarter |

## Valuation & confidence

Estimate = similarity-weighted **median** of adjusted prices; range = weighted
P25–P75.

| grade | meaning |
|---|---|
| A | strong evidence: ≥6 comps, adjusted-price spread ≤6% of the estimate, mean similarity ≥75 |
| B | usable evidence — between the A and C criteria |
| C | weak evidence: ≤3 comps, or spread ≥12% of the estimate |

## Risk flags

| flag | meaning |
|---|---|
| `THIN_COMPS` | fewer than 5 comparable sales support the estimate |
| `HIGH_DISPERSION` | adjusted comp prices spread ≥12% of the estimate — volatile market for this profile |
| `NON_ARMS_LENGTH_EXCLUDED` | excluded suspected non-open-market transfer(s): sold below 75% of assessed value |
| `DATA_CONFLICT` | sources disagreed on a comp's values beyond 0.5%; documented precedence applied, conflict recorded |
| `EXTRAPOLATION` | subject size falls outside the comp set's observed range |
| `STALE_COMPS` | median comp sale is older than 120 days; time adjustments carry more of the estimate |
| `WIDENED_SEARCH` | search criteria were widened to find enough comps; the agent's reasons are logged per round |
| `BASELINE_DIVERGENCE` | estimate differs more than 15% from the market-norm baseline (median $/sqft × subject size; silent under 5 sales) |
