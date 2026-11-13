# Methodology notes

## Data
- **Source:** Yahoo Finance via `yfinance` gives prices and share counts from one place, with no API key.
  Stooq blocks scripted access, so a second-source price comparison was not possible. The data was checked
  directly instead: every name has prices and shares, and the only outsized move is MRNA (+177% on 2026-08-19), which is genuine and kept.
- **Universe:** the current S&P 500 (500 companies). **Period:** 2026-03-19 to 2026-10-19, 148 sessions, 31 weekly rebalances.
- **Limitation:** share counts are a current snapshot (fetched 2026-10-20), not point-in-time, so historical market
  caps are approximate. Using today's constituent list adds survivorship bias.

## Decisions
- **One line per company.** Yahoo reports the company-wide share count on every share class, so Alphabet would
  appear twice in the top 10. Tickers with identical share counts are treated as one company and the
  higher-priced class is kept (GOOGL, FOXA, NWS).
- **Market cap** = split-adjusted close × shares. **Returns** use the dividend-adjusted close.
- **Timing.** Rebalance on the first trading day of each week, using that day's closing ranks. That day's return
  belongs to the old holdings, and the new equal weights apply from the close, so there is no look-ahead.
- **Missing data.** A name without a price on a rebalance day cannot be selected (or retained) that day.
  A held name without a price earns 0 that day, and its next print carries the full move.
- **Weights drift** between rebalances. They are exactly 1/N only on rebalance days.
- **Turnover** is one-way (half the absolute weight change), split into **membership** (names entering or leaving)
  and **reweight** (resetting retained names to 1/N). Reweighting is why turnover is never zero.

## Why the level never jumps
The level moves only by the portfolio return of the previous close's weights. A rebalance changes the weights, never the level.
The tests confirm this independently by recomputing the level from units held × price.

## Stabilisation
- **Rule:** an incumbent stays while ranked ≤ `last_rank + buffer` (70 by default). Vacancies go to the
  best-ranked names not already held. The top-10 exclusion stays strict unless `top_buffer` is set.
- **Result (stabilised vs unstabilised):** avg turnover 3.24% vs 6.52% per rebalance; names added 19 vs 71;
  re-entries within 4 rebalances 4 vs 41; cumulative return 17.16% vs 16.05% gross, 16.96% vs 15.64% after a 10 bps per-side cost estimate.
- **Not a return claim.** The return gap comes from one short period and is sensitive to the buffer size.
- **Trade-off:** less trading, but members may sit at ranks 61–70, so the index is not exactly ranks 11–60.
- **Why 10:** turnover is 6.5% (buffer 0), 3.9% (5), 3.2% (10), 2.6% (20). Most of the benefit is already captured at 10.

## Scaling to 10 years and 5,000 names
Use columnar storage (Parquet/DuckDB), rebuild incrementally from the first changed date, keep point-in-time
prices and share counts, add a security master (share classes, delistings, spin-offs), and add data-quality gates before a build.
