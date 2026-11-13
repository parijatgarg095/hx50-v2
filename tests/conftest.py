from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from hx50.domain import Mandate
from hx50.pipeline.build import build_index
from hx50.pipeline.sources import DataSources
from hx50.storage import IndexReader

from synthetic import SyntheticMarket, make_market


@dataclass
class BuiltIndex:
    db_path: Path
    mandate: Mandate
    market: SyntheticMarket

    @property
    def reader(self) -> IndexReader:
        return IndexReader(self.db_path)

    def sql(self, query: str, params: tuple = ()) -> list[tuple]:
        with sqlite3.connect(self.db_path) as con:
            return con.execute(query, params).fetchall()

    def rebalance_dates(self) -> list[str]:
        return [d for (d,) in self.sql("SELECT date FROM rebalance_dates ORDER BY date")]

    def calendar(self) -> list[str]:
        return [d for (d,) in self.sql("SELECT date FROM calendar ORDER BY date")]


def sources_in(directory: Path) -> DataSources:
    return DataSources(directory / "prices.csv", directory / "shares.csv", directory / "excluded_classes.csv")


@pytest.fixture(scope="session")
def market() -> SyntheticMarket:
    return make_market()


@pytest.fixture(scope="session")
def build(tmp_path_factory, market):
    """Build once per distinct mandate and share the result across the session."""
    cache: dict[Mandate, BuiltIndex] = {}

    def _build(mandate: Mandate = Mandate()) -> BuiltIndex:
        if mandate not in cache:
            directory = market.write(tmp_path_factory.mktemp("build"))
            build_index(sources_in(directory), mandate, directory / "hx50.db")
            cache[mandate] = BuiltIndex(directory / "hx50.db", mandate, market)
        return cache[mandate]

    return _build


@pytest.fixture(scope="session")
def built(build) -> BuiltIndex:
    return build()
