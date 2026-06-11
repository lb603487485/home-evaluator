"""MLS sales feed → canonical frame. Realtor addresses, "3+1" bed notation."""

from pathlib import Path

import pandas as pd

from data.schema import normalize_address


def load(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"beds": str})
    beds = df["beds"].str.partition("+")
    return pd.DataFrame({
        "address_key": df["address"].map(normalize_address),
        "address": df["address"],
        "beds": beds[0].astype(int),
        "beds_bsmt": beds[2].replace("", "0").astype(int),
        "baths": df["baths"].astype(float),
        "sqft": df["sqft"].astype(int),
        "garage_stalls": df["garage_stalls"].astype(int),
        "year_built": df["year_built"].astype(int),
        "sold_price": df["sold_price"].astype(int),
        "sold_date": pd.to_datetime(df["sold_date"]).dt.date,
    })
