-- Published results of one build. The API reads only these tables and never recomputes anything.

CREATE TABLE run (
  run_id        TEXT PRIMARY KEY,
  built_at      TEXT NOT NULL,
  mandate       TEXT NOT NULL,   -- JSON of domain.Mandate
  data_sha256   TEXT NOT NULL,
  code_sha256   TEXT NOT NULL,
  first_date    TEXT NOT NULL,
  last_date     TEXT NOT NULL,
  trading_days  INTEGER NOT NULL,
  universe_size INTEGER NOT NULL,
  runtime       TEXT NOT NULL    -- JSON of library versions
);

CREATE TABLE index_level (
  variant           TEXT NOT NULL,
  date              TEXT NOT NULL,
  level             REAL NOT NULL,
  daily_return      REAL NOT NULL,
  cumulative_return REAL NOT NULL,
  rebalanced        INTEGER NOT NULL,
  PRIMARY KEY (variant, date)
);

-- Weights at each close; they equal 1/size only on rebalance days and drift with prices in between.
CREATE TABLE holding (
  variant         TEXT NOT NULL,
  date            TEXT NOT NULL,
  ticker          TEXT NOT NULL,
  weight          REAL NOT NULL,
  market_cap_rank INTEGER,
  PRIMARY KEY (variant, date, ticker)
);

CREATE TABLE rebalance (
  variant             TEXT NOT NULL,
  date                TEXT NOT NULL,
  added               TEXT NOT NULL,   -- JSON array of tickers
  dropped             TEXT NOT NULL,   -- JSON array of tickers
  membership_turnover REAL NOT NULL,
  reweight_turnover   REAL NOT NULL,
  initial             INTEGER NOT NULL,
  PRIMARY KEY (variant, date)
);

CREATE TABLE scorecard (
  variant             TEXT PRIMARY KEY,
  rebalances          INTEGER NOT NULL,
  avg_turnover        REAL NOT NULL,
  total_turnover      REAL NOT NULL,
  membership_turnover REAL NOT NULL,
  reweight_turnover   REAL NOT NULL,
  names_added         INTEGER NOT NULL,
  names_dropped       INTEGER NOT NULL,
  reentries           INTEGER NOT NULL,
  gross_return        REAL NOT NULL,
  cost_drag           REAL NOT NULL,
  net_return          REAL NOT NULL,
  final_level         REAL NOT NULL
);
