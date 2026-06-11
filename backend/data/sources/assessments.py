"""City assessments → canonical frame. Abbreviated addresses, every property."""

from pathlib import Path

import pandas as pd

from data.schema import normalize_address


def load(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return pd.DataFrame({
        "address_key": df["address"].map(normalize_address),
        "address": df["address"],
        "community": df["community"],
        "property_type": df["property_type"],
        "lat": df["lat"].astype(float),
        "lon": df["lon"].astype(float),
        "year_built": df["year_built"].astype(int),
        "lot_sqft": df["lot_sqft"],  # NaN for apartments; merge converts to None
        "assessed_value": df["assessed_value"].astype(int),
    })
