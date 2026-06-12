# Calibration: fitted factor rates vs engine config

Hedonic fit (numpy lstsq) on 2,603 complete sales, community×type
intercepts, as-of 2026-06-01 · **R² = 0.976**

| Factor | Fitted from sales | Engine (`engine/config.py`) |
|---|---|---|
| size ($/sqft, marginal) | 400 | 182 (ppsf_marginal 0.5 × mean $/sqft 364) |
| bedroom ($) | 8,185 | 8,000 |
| bathroom ($) | 4,185 | 6,000 |
| garage stall ($) | 11,596 | 10,000 |
| age ($/year, newer > older) | 502 | 800 (capped ±20,000) |
| lot ($/sqft) | 2 | 2.0 (beyond 2,000 sqft deadband) |
| market trend ($/quarter) | 7,054 | 1.2%/quarter of price (MARKET_TREND_QOQ) |

Notes: the regression's size coefficient is the *full* hedonic $/sqft;
the engine deliberately applies a *marginal* rate (50% of $/sqft) because
a comp's own price already carries the base size value — standard
appraisal practice, and exactly the kind of judgment a fitted rate must
be reconciled with, not blindly dropped in. Bath/age absorb some size
collinearity.

On synthetic data the fit recovers our own generator's coefficients — the
point is the *mechanism*: the adjustment ladder is linear, so rates fitted
on licensed Pillar 9 solds drop into `ADJ` as a config change. Models
calibrate the explainable engine; they never replace it.
