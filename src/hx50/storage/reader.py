"""Read-side repository over a built database. Each call opens its own read-only connection,
so a concurrent rebuild swapping the file never affects a request already in flight."""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..domain import Holding, LevelPoint, Mandate, Rebalance, Scorecard, Variant
from .models import Composition, Manifest


class IndexNotBuilt(RuntimeError):
    """No database has been built yet."""


class IndexReader:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)

    def is_built(self) -> bool:
        return self._db_path.exists()

    def manifest(self) -> Manifest:
        with self._connect() as con:
            row = con.execute("SELECT * FROM run").fetchone()
        return Manifest(
            run_id=row["run_id"],
            built_at=row["built_at"],
            mandate=Mandate(**json.loads(row["mandate"])),
            data_sha256=row["data_sha256"],
            code_sha256=row["code_sha256"],
            first_date=row["first_date"],
            last_date=row["last_date"],
            trading_days=row["trading_days"],
            universe_size=row["universe_size"],
            runtime=json.loads(row["runtime"]),
        )

    def levels(self, variant: Variant, start: str | None = None, end: str | None = None) -> list[LevelPoint]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT date, level, daily_return, cumulative_return, rebalanced FROM index_level "
                "WHERE variant = ? AND date >= COALESCE(?, date) AND date <= COALESCE(?, date) ORDER BY date",
                (variant.value, start, end),
            ).fetchall()
        return [LevelPoint(r["date"], r["level"], r["daily_return"], r["cumulative_return"], bool(r["rebalanced"]))
                for r in rows]

    def composition(self, variant: Variant, requested: str) -> Composition | None:
        """Holdings at the close of `requested`, or of the latest trading day before it."""
        with self._connect() as con:
            as_of, last_rebalance = con.execute(
                "SELECT (SELECT MAX(date) FROM index_level WHERE variant = :v AND date <= :d), "
                "       (SELECT MAX(date) FROM rebalance WHERE variant = :v AND date <= :d)",
                {"v": variant.value, "d": requested},
            ).fetchone()
            if as_of is None:
                return None
            rows = con.execute(
                "SELECT ticker, weight, market_cap_rank FROM holding WHERE variant = ? AND date = ? "
                "ORDER BY weight DESC, ticker",
                (variant.value, as_of),
            ).fetchall()
        holdings = tuple(Holding(as_of, r["ticker"], r["weight"], r["market_cap_rank"]) for r in rows)
        return Composition(requested, as_of, last_rebalance, holdings)

    def rebalances(self, variant: Variant, start: str | None = None, end: str | None = None) -> list[Rebalance]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT date, added, dropped, membership_turnover, reweight_turnover, initial FROM rebalance "
                "WHERE variant = ? AND date >= COALESCE(?, date) AND date <= COALESCE(?, date) ORDER BY date",
                (variant.value, start, end),
            ).fetchall()
        return [
            Rebalance(r["date"], tuple(json.loads(r["added"])), tuple(json.loads(r["dropped"])),
                      r["membership_turnover"], r["reweight_turnover"], bool(r["initial"]))
            for r in rows
        ]

    def scorecards(self) -> list[Scorecard]:
        with self._connect() as con:
            rows = con.execute("SELECT * FROM scorecard").fetchall()
        return [Scorecard(**{**dict(r), "variant": Variant(r["variant"])}) for r in rows]

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if not self.is_built():
            raise IndexNotBuilt("index not built yet: run `hx50 build`")
        con = sqlite3.connect(f"{self._db_path.resolve().as_uri()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()
