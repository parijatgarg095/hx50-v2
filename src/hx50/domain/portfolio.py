"""Portfolio arithmetic on weight maps: ticker -> fraction of portfolio value (always sums to 1)."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

Weights = Mapping[str, float]
Returns = Mapping[str, float]


def equal_weights(members: Sequence[str]) -> dict[str, float]:
    return dict.fromkeys(members, 1.0 / len(members))


def portfolio_return(weights: Weights, returns: Returns) -> float:
    # A held name with no print today is marked flat; its next print then carries the whole move.
    return sum(w * returns.get(t, 0.0) for t, w in weights.items())


def drift(weights: Weights, returns: Returns, period_return: float) -> dict[str, float]:
    growth = 1.0 + period_return
    return {t: w * (1.0 + returns.get(t, 0.0)) / growth for t, w in weights.items()}


@dataclass(frozen=True)
class Rebalance:
    """Trading needed to move from drifted weights to the new target, split by cause.

    Turnover is one-way (half the absolute weight change): selling X to buy X counts once.
    membership = names entering or leaving; reweight = resetting retained names back to target.
    """

    date: str
    added: tuple[str, ...]
    dropped: tuple[str, ...]
    membership_turnover: float
    reweight_turnover: float
    initial: bool = False

    @property
    def turnover(self) -> float:
        return self.membership_turnover + self.reweight_turnover

    @classmethod
    def construction(cls, date: str, members: Sequence[str]) -> Rebalance:
        return cls(date, tuple(sorted(members)), (), 1.0, 0.0, initial=True)

    @classmethod
    def between(cls, date: str, drifted: Weights, target: Weights) -> Rebalance:
        added = target.keys() - drifted.keys()
        dropped = drifted.keys() - target.keys()
        retained = target.keys() & drifted.keys()
        membership = 0.5 * (sum(target[t] for t in added) + sum(drifted[t] for t in dropped))
        reweight = 0.5 * sum(abs(target[t] - drifted[t]) for t in retained)
        return cls(date, tuple(sorted(added)), tuple(sorted(dropped)), membership, reweight)
