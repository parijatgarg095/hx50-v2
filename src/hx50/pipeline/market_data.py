"""Stage raw CSVs into SQLite, run the SQL model, and read the result back as domain MarketData."""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd

from ..domain import MarketData
from .sources import DataSources

MODEL_SQL = Path(__file__).with_name("model.sql")

PRICE_COLUMNS = ["date", "ticker", "close", "adj_close"]
SHARE_COLUMNS = ["ticker", "shares"]


def stage(con: sqlite3.Connection, sources: DataSources) -> None:
    prices = pd.read_csv(sources.prices, usecols=PRICE_COLUMNS, dtype={"date": str, "ticker": str})
    shares = pd.read_csv(sources.shares, usecols=SHARE_COLUMNS, dtype={"ticker": str})
    excluded = _read_excluded(sources.excluded_classes)

    prices.to_sql("raw_prices", con, if_exists="replace", index=False)
    shares.to_sql("raw_shares", con, if_exists="replace", index=False)
    excluded.to_sql("raw_excluded", con, if_exists="replace", index=False)
    con.executescript(MODEL_SQL.read_text(encoding="utf-8"))


def load_market(con: sqlite3.Connection) -> MarketData:
    calendar = tuple(d for (d,) in con.execute("SELECT date FROM calendar ORDER BY date"))
    rebalance_dates = frozenset(d for (d,) in con.execute("SELECT date FROM rebalance_dates"))

    ranks: dict[str, dict[str, int]] = defaultdict(dict)
    for day, ticker, rank in con.execute("SELECT date, ticker, rank FROM ranked"):
        ranks[day][ticker] = rank

    returns: dict[str, dict[str, float]] = defaultdict(dict)
    for day, ticker, ret in con.execute("SELECT date, ticker, ret FROM returns"):
        returns[day][ticker] = ret

    (universe_size,) = con.execute("SELECT COUNT(DISTINCT ticker) FROM market_cap").fetchone()
    return MarketData(calendar, rebalance_dates, dict(ranks), dict(returns), universe_size)


def _read_excluded(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame({"ticker": pd.Series(dtype=str)})
    return pd.read_csv(path, usecols=["ticker"], dtype={"ticker": str})
