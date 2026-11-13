"""HTTP contract. Kept separate from domain types so the wire format can evolve independently."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from ..domain import Variant


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MandateOut(Schema):
    size: int
    exclude_top: int
    buffer: int
    top_buffer: int
    base_level: float
    cost_bps: float
    reentry_window: int
    first_rank: int
    last_rank: int
    retention_floor: int


class MandateIn(BaseModel):
    size: int = Field(50, ge=1, le=500, description="Number of constituents")
    exclude_top: int = Field(10, ge=0, le=500, description="Largest names excluded")
    buffer: int = Field(10, ge=0, le=500, description="Extra ranks an incumbent may slip before removal")
    top_buffer: int = Field(0, ge=0, le=500, description="Ranks an incumbent may climb into the excluded top")


class RunOut(Schema):
    run_id: str
    built_at: str
    mandate: MandateOut
    data_sha256: str
    code_sha256: str
    first_date: dt.date
    last_date: dt.date
    trading_days: int
    universe_size: int
    runtime: dict[str, str]


class LevelPointOut(Schema):
    date: dt.date
    level: float
    daily_return: float
    cumulative_return: float
    rebalanced: bool


class HoldingOut(Schema):
    ticker: str
    weight: float
    market_cap_rank: int | None


class CompositionOut(Schema):
    requested: dt.date
    as_of: dt.date
    last_rebalance: dt.date
    rebalance_day: bool
    count: int
    weight_sum: float
    holdings: list[HoldingOut]


class RebalanceOut(Schema):
    date: dt.date
    initial: bool
    turnover: float
    membership_turnover: float
    reweight_turnover: float
    added: list[str]
    dropped: list[str]


class ScorecardOut(Schema):
    variant: Variant
    rebalances: int
    avg_turnover: float
    total_turnover: float
    membership_turnover: float
    reweight_turnover: float
    names_added: int
    names_dropped: int
    reentries: int
    gross_return: float
    cost_drag: float
    net_return: float
    final_level: float


class RebuildOut(Schema):
    run: RunOut
    scorecard: list[ScorecardOut]


class ErrorOut(BaseModel):
    detail: str
