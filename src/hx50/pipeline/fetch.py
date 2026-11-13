"""Download index inputs from public sources (needs internet and the `fetch` extra).

Universe: current S&P 500 list from Wikipedia. Prices: Yahoo daily bars. Shares: Yahoo's current snapshot,
which is not point-in-time, so historical market caps are approximate and the universe has survivorship bias.
"""
from __future__ import annotations

import io
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date

import pandas as pd

UNIVERSE_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
USER_AGENT = "Mozilla/5.0 (hx50-data-fetch)"
SHARE_RETRIES = 3
SHARE_THREADS = 8


@dataclass(frozen=True)
class FetchResult:
    universe: pd.DataFrame
    prices: pd.DataFrame
    shares: pd.DataFrame


def fetch_all(start: str, end: str) -> FetchResult:
    universe = fetch_universe()
    prices = fetch_prices(universe["ticker"].tolist(), start, end)
    shares = fetch_shares(prices["ticker"].unique().tolist())
    return FetchResult(universe, prices, shares)


def fetch_universe() -> pd.DataFrame:
    import requests

    html = requests.get(UNIVERSE_URL, headers={"User-Agent": USER_AGENT}, timeout=30).text
    table = pd.read_html(io.StringIO(html))[0]
    table = table.rename(columns={"Symbol": "symbol", "Security": "name", "GICS Sector": "sector"})
    table["ticker"] = table["symbol"].str.replace(".", "-", regex=False)  # BRK.B -> BRK-B, Yahoo's spelling
    return table[["ticker", "name", "sector"]]


def fetch_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(tickers, start=start, end=end, auto_adjust=False, group_by="ticker",
                      threads=True, progress=False)
    available = set(raw.columns.get_level_values(0))
    frames = []
    for ticker in (t for t in tickers if t in available):
        frame = raw[ticker][["Close", "Adj Close"]].dropna().reset_index()
        frame.columns = ["date", "close", "adj_close"]
        frame["ticker"] = ticker
        frames.append(frame)
    prices = pd.concat(frames, ignore_index=True)
    prices["date"] = pd.to_datetime(prices["date"]).dt.strftime("%Y-%m-%d")
    return prices[["date", "ticker", "close", "adj_close"]]


def fetch_shares(tickers: list[str]) -> pd.DataFrame:
    with ThreadPoolExecutor(SHARE_THREADS) as pool:
        counts = list(pool.map(_share_count, tickers))
    shares = pd.DataFrame(counts, columns=["ticker", "shares"]).dropna()
    shares["asof"] = date.today().isoformat()
    shares["source"] = "yfinance fast_info.shares (current snapshot)"
    return shares


def _share_count(ticker: str) -> tuple[str, float | None]:
    import yfinance as yf

    # Yahoo fails intermittently; back off linearly and treat persistent failure as "unknown".
    for attempt in range(SHARE_RETRIES):
        try:
            count = yf.Ticker(ticker).fast_info["shares"]
            return ticker, float(count) if count and count > 0 else None
        except Exception:
            time.sleep(1 + attempt)
    return ticker, None
