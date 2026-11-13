"""One line per company.

Yahoo reports the company's total share count on every listed class (GOOGL and GOOG both show the full count),
so price x shares values each class at the whole company's cap and dual-class companies would be ranked twice.
Tickers with an identical share count are treated as one company; the higher-priced class is kept.
"""
from __future__ import annotations

import pandas as pd

COLUMNS = ["ticker", "kept_ticker", "reason"]


def secondary_share_classes(shares: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    last_close = prices.sort_values("date").groupby("ticker")["close"].last()
    rows = []
    for _, group in shares.dropna(subset=["shares"]).groupby("shares"):
        tickers = list(group["ticker"])
        if len(tickers) < 2:
            continue
        kept = max(tickers, key=lambda t: (last_close.get(t, 0.0), t))
        rows += [
            {"ticker": t, "kept_ticker": kept, "reason": "same company, secondary share class"}
            for t in tickers
            if t != kept
        ]
    return pd.DataFrame(rows, columns=COLUMNS)
