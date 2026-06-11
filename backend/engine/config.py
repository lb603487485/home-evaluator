"""Every engine tunable lives here — weights, rates, filters, confidence cuts.

Values are final per the implementation plan unless eval (Task 10) disproves them.
"""

WEIGHTS = {"distance": 25, "recency": 20, "sqft": 20, "beds_baths": 10,
           "year_built": 10, "lot": 5, "garage": 5, "same_community": 5}

FILTER_DEFAULTS = dict(radius_km=2.0, days=180, sqft_pct=0.25, beds_delta=1)

WIDENING_MOVES = {"extend_days": (+90, 365), "widen_radius": (1.5, 5.0),
                  "relax_sqft": (0.35,), "relax_beds": (2,)}  # (step, cap)

MIN_COMPS, TOP_N_REVIEW, MAX_WIDEN_ROUNDS = 5, 8, 2

ADJ = dict(ppsf_marginal=0.5, bed=8_000, bath=6_000, garage=10_000,
           age_per_year=800, age_cap=20_000, lot_per_sqft=2.0, lot_deadband=2_000)

CONFIDENCE = dict(A=dict(min_comps=6, max_iqr=0.06, min_sim=75),
                  C=dict(max_comps=3, min_iqr=0.12))  # B = else

NON_ARMS_LENGTH_RATIO = 0.75  # price/assessed below this ⇒ suspect
PRICE_CONFLICT_TOL = 0.005    # >0.5% MLS vs land-titles delta ⇒ Conflict
