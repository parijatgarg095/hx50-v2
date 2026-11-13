"""Day-by-day index simulation.

The level moves only by the return of the weights held at the previous close:
    r_t = sum_i w_i(t-1) * ret_i(t),    L_t = L_{t-1} * (1 + r_t)
A rebalance swaps weights at the close and never touches the level, so membership changes cannot cause jumps.
On a rebalance day the old holdings earn that day's return and the new selection uses that close's ranks,
so there is no look-ahead.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .mandate import Mandate
from .portfolio import Rebalance, Weights, drift, equal_weights, portfolio_return
from .selection import Variant, rule_for


@dataclass(frozen=True)
class MarketData:
    calendar: tuple[str, ...]
    rebalance_dates: frozenset[str]
    ranks: Mapping[str, Mapping[str, int]]        # date -> ticker -> market-cap rank, 1 = largest
    returns: Mapping[str, Mapping[str, float]]    # date -> ticker -> total return since previous print
    universe_size: int

    def ranks_on(self, date: str) -> Mapping[str, int]:
        return self.ranks.get(date, {})

    def returns_on(self, date: str) -> Mapping[str, float]:
        return self.returns.get(date, {})


@dataclass(frozen=True)
class LevelPoint:
    date: str
    level: float
    daily_return: float
    cumulative_return: float
    rebalanced: bool


@dataclass(frozen=True)
class Holding:
    date: str
    ticker: str
    weight: float
    market_cap_rank: int | None


@dataclass(frozen=True)
class IndexHistory:
    variant: Variant
    levels: tuple[LevelPoint, ...]
    holdings: tuple[Holding, ...]
    rebalances: tuple[Rebalance, ...]


def simulate(market: MarketData, mandate: Mandate, variant: Variant) -> IndexHistory:
    if not market.calendar:
        raise ValueError("market data contains no trading days")
    rule = rule_for(variant, mandate)
    levels: list[LevelPoint] = []
    holdings: list[Holding] = []
    rebalances: list[Rebalance] = []

    first_day, *later_days = market.calendar
    members = rule.select(market.ranks_on(first_day), [])
    weights: Weights = equal_weights(members)
    level = mandate.base_level
    rebalances.append(Rebalance.construction(first_day, members))
    levels.append(_level_point(first_day, level, 0.0, mandate, rebalanced=True))
    holdings.extend(_holdings(first_day, weights, market))

    for day in later_days:
        day_returns = market.returns_on(day)
        daily_return = portfolio_return(weights, day_returns)
        level *= 1.0 + daily_return
        drifted = drift(weights, day_returns, daily_return)

        is_rebalance = day in market.rebalance_dates
        if is_rebalance:
            members = rule.select(market.ranks_on(day), members)
            target = equal_weights(members)
            rebalances.append(Rebalance.between(day, drifted, target))
            weights = target
        else:
            weights = drifted

        levels.append(_level_point(day, level, daily_return, mandate, rebalanced=is_rebalance))
        holdings.extend(_holdings(day, weights, market))

    return IndexHistory(variant, tuple(levels), tuple(holdings), tuple(rebalances))


def _level_point(day: str, level: float, daily_return: float, mandate: Mandate, *, rebalanced: bool) -> LevelPoint:
    return LevelPoint(day, level, daily_return, level / mandate.base_level - 1.0, rebalanced)


def _holdings(day: str, weights: Weights, market: MarketData) -> list[Holding]:
    ranks = market.ranks_on(day)
    return [Holding(day, ticker, weight, ranks.get(ticker)) for ticker, weight in weights.items()]
