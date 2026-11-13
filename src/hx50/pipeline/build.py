"""Full deterministic build: CSV -> SQL model -> both variants -> persisted run.

The build writes to a staging file and swaps it in with os.replace, so readers see either the previous run
or the new one, never a half-written database, and a failed build leaves the served index untouched.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..domain import Mandate, MarketData, Scorecard, Variant, simulate
from ..storage import Manifest, write_run
from .market_data import MODEL_SQL, load_market, stage
from .sources import DataSources, sha256_of

DOMAIN_DIR = Path(__file__).resolve().parent.parent / "domain"


def build_index(sources: DataSources, mandate: Mandate, db_path: Path) -> tuple[Manifest, list[Scorecard]]:
    db_path = Path(db_path)
    staging = db_path.with_name(db_path.name + ".building")
    staging.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(staging)) as con:
            stage(con, sources)
            market = load_market(con)
            mandate.ensure_fits(market.universe_size)
            histories = [simulate(market, mandate, variant) for variant in Variant]
            scorecards = [Scorecard.of(history, mandate) for history in histories]
            manifest = _manifest(mandate, sources, market)
            write_run(con, manifest, histories, scorecards)
            con.commit()
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    os.replace(staging, db_path)
    return manifest, scorecards


def code_fingerprint() -> str:
    return sha256_of([*sorted(DOMAIN_DIR.glob("*.py")), MODEL_SQL])


def _manifest(mandate: Mandate, sources: DataSources, market: MarketData) -> Manifest:
    data_sha = sources.fingerprint()
    code_sha = code_fingerprint()
    # Same rules + same data + same code => same run id, which makes any published number reproducible.
    identity = json.dumps([mandate.to_dict(), data_sha, code_sha], sort_keys=True).encode()
    return Manifest(
        run_id=hashlib.sha256(identity).hexdigest()[:12],
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        mandate=mandate,
        data_sha256=data_sha,
        code_sha256=code_sha,
        first_date=market.calendar[0],
        last_date=market.calendar[-1],
        trading_days=len(market.calendar),
        universe_size=market.universe_size,
        runtime={"python": platform.python_version(), "pandas": pd.__version__, "sqlite": sqlite3.sqlite_version},
    )
