"""Persist one build into a fresh database."""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from ..domain import IndexHistory, Scorecard
from .models import Manifest

SCHEMA_SQL = Path(__file__).with_name("schema.sql")


def write_run(
    con: sqlite3.Connection,
    manifest: Manifest,
    histories: Sequence[IndexHistory],
    scorecards: Sequence[Scorecard],
) -> None:
    con.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    _write_manifest(con, manifest)
    for history in histories:
        _write_history(con, history)
    con.executemany(
        "INSERT INTO scorecard VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (s.variant.value, s.rebalances, s.avg_turnover, s.total_turnover, s.membership_turnover,
             s.reweight_turnover, s.names_added, s.names_dropped, s.reentries, s.gross_return,
             s.cost_drag, s.net_return, s.final_level)
            for s in scorecards
        ],
    )


def _write_manifest(con: sqlite3.Connection, m: Manifest) -> None:
    con.execute(
        "INSERT INTO run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (m.run_id, m.built_at, json.dumps(m.mandate.to_dict()), m.data_sha256, m.code_sha256,
         m.first_date, m.last_date, m.trading_days, m.universe_size, json.dumps(m.runtime)),
    )


def _write_history(con: sqlite3.Connection, history: IndexHistory) -> None:
    variant = history.variant.value
    con.executemany(
        "INSERT INTO index_level VALUES (?, ?, ?, ?, ?, ?)",
        [(variant, p.date, p.level, p.daily_return, p.cumulative_return, int(p.rebalanced)) for p in history.levels],
    )
    con.executemany(
        "INSERT INTO holding VALUES (?, ?, ?, ?, ?)",
        [(variant, h.date, h.ticker, h.weight, h.market_cap_rank) for h in history.holdings],
    )
    con.executemany(
        "INSERT INTO rebalance VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (variant, r.date, json.dumps(r.added), json.dumps(r.dropped),
             r.membership_turnover, r.reweight_turnover, int(r.initial))
            for r in history.rebalances
        ],
    )
