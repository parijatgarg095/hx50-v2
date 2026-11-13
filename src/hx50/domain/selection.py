"""Constituent selection: one rule per index variant (Strategy), so the simulation never branches on variant."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .mandate import Mandate

Ranks = Mapping[str, int]


class Variant(str, Enum):
    STABILISED = "stabilised"
    RAW = "raw"


class InsufficientUniverse(ValueError):
    """Fewer eligible names than seats on a rebalance date."""


class SelectionRule(Protocol):
    def select(self, ranks: Ranks, incumbents: Sequence[str]) -> list[str]: ...


def eligible_by_rank(ranks: Ranks, mandate: Mandate) -> list[str]:
    eligible = sorted((t for t, r in ranks.items() if mandate.is_eligible(r)), key=ranks.__getitem__)
    if len(eligible) < mandate.size:
        raise InsufficientUniverse(f"only {len(eligible)} eligible names, mandate needs {mandate.size}")
    return eligible


@dataclass(frozen=True)
class StrictRule:
    """Holds exactly ranks first_rank..last_rank."""

    mandate: Mandate

    def select(self, ranks: Ranks, incumbents: Sequence[str]) -> list[str]:
        return eligible_by_rank(ranks, self.mandate)[: self.mandate.size]


@dataclass(frozen=True)
class BufferedRule:
    """Incumbents stay while inside the retention band; vacancies go to the best-ranked newcomers."""

    mandate: Mandate

    def select(self, ranks: Ranks, incumbents: Sequence[str]) -> list[str]:
        candidates = eligible_by_rank(ranks, self.mandate)
        if not incumbents:
            return candidates[: self.mandate.size]
        # An unranked incumbent had no price today, so it cannot prove it is still inside the band.
        kept = sorted(
            (t for t in incumbents if t in ranks and self.mandate.is_retained(ranks[t])),
            key=ranks.__getitem__,
        )
        kept_set = set(kept)
        vacancies = self.mandate.size - len(kept)
        newcomers = [t for t in candidates if t not in kept_set][:vacancies]
        return kept + newcomers


_RULES: dict[Variant, type[StrictRule] | type[BufferedRule]] = {
    Variant.STABILISED: BufferedRule,
    Variant.RAW: StrictRule,
}


def rule_for(variant: Variant, mandate: Mandate) -> SelectionRule:
    return _RULES[variant](mandate)
