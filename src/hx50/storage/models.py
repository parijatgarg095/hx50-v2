"""Read models: shapes the storage layer returns that are not domain concepts themselves."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..domain import Holding, Mandate


@dataclass(frozen=True)
class Manifest:
    run_id: str
    built_at: str
    mandate: Mandate
    data_sha256: str
    code_sha256: str
    first_date: str
    last_date: str
    trading_days: int
    universe_size: int
    runtime: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Composition:
    requested: str
    as_of: str
    last_rebalance: str
    holdings: tuple[Holding, ...]

    @property
    def rebalance_day(self) -> bool:
        return self.as_of == self.last_rebalance

    @property
    def count(self) -> int:
        return len(self.holdings)

    @property
    def weight_sum(self) -> float:
        return sum(h.weight for h in self.holdings)
