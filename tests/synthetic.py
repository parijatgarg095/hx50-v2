"""Synthetic market that guarantees the awkward cases: a Monday holiday, missing prices, many rank crossings."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

HOLIDAY = "2026-01-19"   # a Monday
LAST_BEFORE_HOLIDAY = "2026-01-16"
FIRST_AFTER_HOLIDAY = "2026-01-20"


@dataclass
class SyntheticMarket:
    prices: pd.DataFrame
    shares: pd.DataFrame

    def write(self, directory: Path, excluded: pd.DataFrame | None = None) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        self.prices.to_csv(directory / "prices.csv", index=False)
        self.shares.to_csv(directory / "shares.csv", index=False)
        if excluded is not None:
            excluded.to_csv(directory / "excluded_classes.csv", index=False)
        return directory

    def price_matrix(self) -> pd.DataFrame:
        return self.prices.pivot(index="date", columns="ticker", values="adj_close").sort_index().ffill()


def make_market(n_tickers: int = 120, n_days: int = 130, seed: int = 7) -> SyntheticMarket:
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2026-01-05", periods=n_days + 1)
    days = days.delete(days.get_loc(pd.Timestamp(HOLIDAY)))[:n_days]
    tickers = [f"T{i:03d}" for i in range(n_tickers)]
    shares = rng.uniform(0.5e9, 5e9, n_tickers)
    start_prices = rng.uniform(20, 400, n_tickers)
    paths = start_prices * np.cumprod(1 + rng.normal(0.0004, 0.02, (n_days, n_tickers)), axis=0)

    rows = [(d.strftime("%Y-%m-%d"), t, paths[i, j], paths[i, j]) for j, t in enumerate(tickers) for i, d in enumerate(days)]
    prices = pd.DataFrame(rows, columns=["date", "ticker", "close", "adj_close"])
    missing = rng.choice(len(prices), size=60, replace=False)
    prices = prices.drop(prices.index[missing]).reset_index(drop=True)
    return SyntheticMarket(prices, pd.DataFrame({"ticker": tickers, "shares": shares}))
