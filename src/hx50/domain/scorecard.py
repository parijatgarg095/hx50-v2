"""Comparison metrics for one index variant. Initial construction is excluded: it is 100% turnover by definition."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .mandate import Mandate
from .portfolio import Rebalance
from .selection import Variant
from .simulation import IndexHistory

BPS = 10_000


@dataclass(frozen=True)
class Scorecard:
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

    @classmethod
    def of(cls, history: IndexHistory, mandate: Mandate) -> Scorecard:
        periodic = [r for r in history.rebalances if not r.initial]
        total_turnover = sum(r.turnover for r in periodic)
        gross_return = history.levels[-1].cumulative_return
        # One-way turnover is a sell plus a buy of the same size, and each side pays cost_bps.
        # Subtracted once at the end: a first-order estimate that ignores compounding of costs.
        cost_drag = 2.0 * total_turnover * mandate.cost_bps / BPS
        return cls(
            variant=history.variant,
            rebalances=len(periodic),
            avg_turnover=total_turnover / len(periodic) if periodic else 0.0,
            total_turnover=total_turnover,
            membership_turnover=sum(r.membership_turnover for r in periodic),
            reweight_turnover=sum(r.reweight_turnover for r in periodic),
            names_added=sum(len(r.added) for r in periodic),
            names_dropped=sum(len(r.dropped) for r in periodic),
            reentries=count_reentries(periodic, mandate.reentry_window),
            gross_return=gross_return,
            cost_drag=cost_drag,
            net_return=gross_return - cost_drag,
            final_level=history.levels[-1].level,
        )


def count_reentries(rebalances: Sequence[Rebalance], window: int) -> int:
    """Names bought back within `window` rebalances of being dropped: the round-trip churn a buffer targets."""
    last_dropped: dict[str, int] = {}
    reentries = 0
    for position, rebalance in enumerate(rebalances):
        reentries += sum(1 for t in rebalance.added if t in last_dropped and position - last_dropped[t] <= window)
        last_dropped.update(dict.fromkeys(rebalance.dropped, position))
    return reentries
