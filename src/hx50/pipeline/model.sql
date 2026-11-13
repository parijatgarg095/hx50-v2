-- HX-50 data model: all cleaning and ranking happens here; Python only runs the index rules.
-- Inputs: raw_prices(date, ticker, close, adj_close), raw_shares(ticker, shares), raw_excluded(ticker).
-- Flow:   raw_prices -> prices -> calendar -> market_cap -> ranked
--                              -> returns
--         calendar   -> rebalance_dates

DROP TABLE IF EXISTS prices;
DROP TABLE IF EXISTS calendar;
DROP TABLE IF EXISTS market_cap;
DROP TABLE IF EXISTS ranked;
DROP TABLE IF EXISTS returns;
DROP TABLE IF EXISTS rebalance_dates;

-- close is split-adjusted (sizes the company); adj_close also folds in dividends (drives returns).
CREATE TABLE prices AS
SELECT date, ticker, MAX(close) AS close, MAX(adj_close) AS adj_close
FROM raw_prices
WHERE close > 0 AND adj_close > 0
GROUP BY date, ticker;
CREATE INDEX ix_prices ON prices (ticker, date);

-- A trading day needs at least half the usual cross-section, so a stray partial row cannot invent one.
CREATE TABLE calendar AS
SELECT date
FROM prices
GROUP BY date
HAVING COUNT(*) >= 0.5 * (SELECT MAX(n) FROM (SELECT COUNT(*) AS n FROM prices GROUP BY date))
ORDER BY date;

-- Current share count x historical close: an approximation, since point-in-time share counts are unavailable.
-- A name with no price or no share count on a date has no row, which makes it ineligible that day.
CREATE TABLE market_cap AS
SELECT p.date, p.ticker, p.close * s.shares AS market_cap
FROM prices AS p
JOIN raw_shares AS s ON s.ticker = p.ticker AND s.shares > 0
JOIN calendar AS c ON c.date = p.date
WHERE p.ticker NOT IN (SELECT ticker FROM raw_excluded);

-- Ticker breaks ties so ranks are fully deterministic.
CREATE TABLE ranked AS
SELECT date, ticker, market_cap,
       ROW_NUMBER() OVER (PARTITION BY date ORDER BY market_cap DESC, ticker) AS rank
FROM market_cap;
CREATE INDEX ix_ranked ON ranked (date);

-- LAG runs over each ticker's own rows, so after a missing day the return spans the gap
-- (equivalent to forward-filling the price).
CREATE TABLE returns AS
SELECT date, ticker, ret
FROM (
  SELECT p.date, p.ticker,
         p.adj_close / LAG(p.adj_close) OVER (PARTITION BY p.ticker ORDER BY p.date) - 1.0 AS ret
  FROM prices AS p
  JOIN calendar AS c ON c.date = p.date
)
WHERE ret IS NOT NULL;
CREATE INDEX ix_returns ON returns (date);

-- First real trading day of each Monday-based week: a Monday holiday moves the rebalance to Tuesday.
-- For monthly rebalancing, group by strftime('%Y-%m', date) instead of week_start.
CREATE TABLE rebalance_dates AS
SELECT MIN(date) AS date
FROM (
  SELECT date,
         date(date, '-' || ((CAST(strftime('%w', date) AS INTEGER) + 6) % 7) || ' days') AS week_start
  FROM calendar
)
GROUP BY week_start
ORDER BY date;
