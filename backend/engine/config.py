"""Every engine tunable lives here — weights, rates, filters, confidence cuts.

Values are final per the implementation plan unless eval (Task 10) disproves them.
"""

WEIGHTS = {"distance": 25, "recency": 20, "sqft": 20, "beds_baths": 10,
           "year_built": 10, "lot": 5, "garage": 5, "same_community": 5}

FILTER_DEFAULTS = dict(radius_km=2.0, days=180, sqft_pct=0.25, beds_delta=1)

WIDENING_MOVES = {"extend_days": (+90, 365), "widen_radius": (1.5, 5.0),
                  "relax_sqft": (0.35,), "relax_beds": (2,)}  # (step, cap)

MIN_COMPS, TOP_N_REVIEW, MAX_WIDEN_ROUNDS = 5, 8, 2

# Similarity sub-score normalizers: delta at which a dimension's closeness hits 0
SCORE_NORM = dict(distance_km=5.0, recency_days=365.0, sqft_band_pct=0.35,
                  beds_baths=4.0, year_years=30.0, lot_sqft=10_000.0,
                  garage_stalls=2.0)

ADJ = dict(ppsf_marginal=0.5, bed=8_000, bath=6_000, garage=10_000,
           age_per_year=800, age_cap=20_000, lot_per_sqft=2.0, lot_deadband=2_000)

CONFIDENCE = dict(A=dict(min_comps=6, max_iqr=0.06, min_sim=75),
                  C=dict(max_comps=3, min_iqr=0.12))  # B = else

NON_ARMS_LENGTH_RATIO = 0.75  # price/assessed below this ⇒ suspect
PRICE_CONFLICT_TOL = 0.005    # >0.5% MLS vs land-titles delta ⇒ Conflict
STALE_DAYS = 120              # median comp age beyond this ⇒ STALE_COMPS
FLIP_WINDOW_DAYS = 183        # resale gap under this …
FLIP_GAIN_SUSPECT = 1.15      # … with price gain over this ⇒ quick-flip suspect

# Market-norm baseline check (the honest AVM stand-in — production swaps the
# $/sqft median for a model; the divergence rule and wiring don't change).
BASELINE_TOLERANCE = 0.15     # |estimate vs $/sqft yardstick| beyond this ⇒ flag
BASELINE_MIN_SAMPLE = 5       # fewer recent sales than this ⇒ yardstick unreliable, stay silent

# Quarterly trend index the engine subscribes to (production: CREA/Teranet HPI).
# Calibrated to the synthetic world's drift; used for time adjustments.
MARKET_TREND_QOQ = {"Beltline": 0.018, "Bridgeland": 0.012, "Killarney": 0.012,
                    "Tuscany": 0.012, "Evanston": 0.012, "Auburn Bay": 0.012,
                    "Aspen Woods": 0.012, "Bearspaw": 0.006}
DAYS_PER_QUARTER = 91.25
