"""Land-titles transfers → canonical frame. Legal addresses ("PLAN .. BLK .. LOT ..; CIVIC")."""

from pathlib import Path

import pandas as pd

from data.schema import normalize_address


def load(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    civic = df["legal_address"].str.split(";", n=1).str[1]
    return pd.DataFrame({
        "address_key": civic.map(normalize_address),
        "sold_price": df["transfer_price"].astype(int),
        "sold_date": pd.to_datetime(df["transfer_date"]).dt.date,
    })
