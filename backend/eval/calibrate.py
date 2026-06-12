"""ML calibration pipeline demo: fit per-factor $ effects by hedonic regression
(numpy lstsq) on the sales data and compare against the hand-set engine rates in
`engine/config.py`. Writes eval/calibration.md.

    uv run python -m eval.calibrate

Framing (per spec §8 / demo-notes): on synthetic data the fit *recovers our own
generator's truth* — the point is the mechanism, not a quality claim. On licensed
Pillar 9 solds the same code fits the real market and the fitted rates drop into
`ADJ` as a config change. Models calibrate the engine; they never replace it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from data.store import ensure_comps
from engine.config import ADJ, DAYS_PER_QUARTER, MARKET_TREND_QOQ


def load_frame() -> pd.DataFrame:
    df = pd.read_parquet(ensure_comps())
    df = df.dropna(subset=["sold_price", "sold_date", "sqft", "beds", "baths",
                           "year_built"])
    df["sold_date"] = pd.to_datetime(df["sold_date"])
    df["lot_sqft"] = df["lot_sqft"].fillna(0.0)
    return df


def fit(df: pd.DataFrame) -> dict:
    as_of = df["sold_date"].max()
    days_ago = (as_of - df["sold_date"]).dt.days.to_numpy(dtype=float)

    cols = {
        "sqft": df["sqft"].to_numpy(dtype=float),
        "beds": df["beds"].to_numpy(dtype=float),
        "baths": df["baths"].to_numpy(dtype=float),
        "garage": df["garage_stalls"].to_numpy(dtype=float),
        "age_years": (as_of.year - df["year_built"]).to_numpy(dtype=float),
        "lot_sqft": df["lot_sqft"].to_numpy(dtype=float),
        "days_ago": days_ago,
    }
    # community × type intercepts soak up level differences so the factor
    # coefficients measure marginal $ effects — same shape as the ADJ ladder
    dummies = pd.get_dummies(df["community"] + "·" + df["property_type"],
                             dtype=float)
    X = np.column_stack(list(cols.values()) + [dummies.to_numpy()])
    y = df["sold_price"].to_numpy(dtype=float)

    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    fitted = dict(zip(cols.keys(), coef[:len(cols)]))
    r2 = 1 - np.sum((y - X @ coef) ** 2) / np.sum((y - y.mean()) ** 2)

    mean_ppsf = float((df["sold_price"] / df["sqft"]).mean())
    return {"fitted": fitted, "r2": float(r2), "n": len(df),
            "mean_ppsf": mean_ppsf, "as_of": as_of.date()}


def render(res: dict) -> str:
    f = res["fitted"]
    engine_sqft = ADJ["ppsf_marginal"] * res["mean_ppsf"]
    # the time coefficient is $/day-ago; flip sign and scale to $/quarter
    pct_per_quarter = -f["days_ago"] * DAYS_PER_QUARTER
    rows = [
        ("size ($/sqft, marginal)", f["sqft"],
         f"{engine_sqft:,.0f} (ppsf_marginal {ADJ['ppsf_marginal']} × mean $/sqft {res['mean_ppsf']:,.0f})"),
        ("bedroom ($)", f["beds"], f"{ADJ['bed']:,}"),
        ("bathroom ($)", f["baths"], f"{ADJ['bath']:,}"),
        ("garage stall ($)", f["garage"], f"{ADJ['garage']:,}"),
        ("age ($/year, newer > older)", -f["age_years"],
         f"{ADJ['age_per_year']:,} (capped ±{ADJ['age_cap']:,})"),
        ("lot ($/sqft)", f["lot_sqft"],
         f"{ADJ['lot_per_sqft']} (beyond {ADJ['lot_deadband']:,} sqft deadband)"),
        ("market trend ($/quarter)", pct_per_quarter,
         f"{np.median(list(MARKET_TREND_QOQ.values())):.1%}/quarter of price (MARKET_TREND_QOQ)"),
    ]
    lines = [
        "# Calibration: fitted factor rates vs engine config",
        "",
        f"Hedonic fit (numpy lstsq) on {res['n']:,} complete sales, community×type",
        f"intercepts, as-of {res['as_of']} · **R² = {res['r2']:.3f}**",
        "",
        "| Factor | Fitted from sales | Engine (`engine/config.py`) |",
        "|---|---|---|",
    ]
    lines += [f"| {name} | {value:,.0f} | {engine} |" for name, value, engine in rows]
    lines += [
        "",
        "Notes: the regression's size coefficient is the *full* hedonic $/sqft;",
        "the engine deliberately applies a *marginal* rate (50% of $/sqft) because",
        "a comp's own price already carries the base size value — standard",
        "appraisal practice, and exactly the kind of judgment a fitted rate must",
        "be reconciled with, not blindly dropped in. Bath/age absorb some size",
        "collinearity.",
        "",
        "On synthetic data the fit recovers our own generator's coefficients — the",
        "point is the *mechanism*: the adjustment ladder is linear, so rates fitted",
        "on licensed Pillar 9 solds drop into `ADJ` as a config change. Models",
        "calibrate the explainable engine; they never replace it.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    res = fit(load_frame())
    md = render(res)
    out = Path(__file__).parent / "calibration.md"
    out.write_text(md)
    print(md)
    print(f"→ {out}")


if __name__ == "__main__":
    main()
