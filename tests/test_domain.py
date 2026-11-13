"""Unit tests for the pure domain: no files, no database."""
from __future__ import annotations

import pytest

from hx50.domain import InsufficientUniverse, InvalidMandate, Mandate, MarketData, Rebalance, Variant, simulate
from hx50.domain.portfolio import drift, equal_weights, portfolio_return
from hx50.domain.scorecard import count_reentries
from hx50.domain.selection import BufferedRule, StrictRule

RANKS = {f"S{i:02d}": i for i in range(1, 81)}


class TestMandate:
    def test_defaults_describe_ranks_11_to_60_with_buffer_to_70(self):
        m = Mandate()
        assert (m.first_rank, m.last_rank, m.retention_floor) == (11, 60, 70)

    @pytest.mark.parametrize("change", [{"size": 0}, {"buffer": -1}, {"top_buffer": 11}, {"base_level": 0}])
    def test_rejects_impossible_rules(self, change):
        with pytest.raises(InvalidMandate):
            Mandate(**change)

    def test_must_fit_the_universe(self):
        with pytest.raises(InvalidMandate):
            Mandate(size=50, exclude_top=10).ensure_fits(universe_size=59)


class TestSelection:
    def test_strict_rule_holds_exactly_the_entry_band(self):
        selected = StrictRule(Mandate()).select(RANKS, [])
        assert sorted(RANKS[t] for t in selected) == list(range(11, 61))

    def test_buffered_rule_keeps_incumbents_inside_the_band(self):
        incumbents = [f"S{i:02d}" for i in range(15, 65)]          # 61..64 have slipped, still within 70
        selected = BufferedRule(Mandate()).select(RANKS, incumbents)
        assert set(selected) == set(incumbents)

    def test_buffered_rule_replaces_names_below_the_floor_with_best_newcomers(self):
        incumbents = [f"S{i:02d}" for i in range(11, 60)] + ["S75"]
        selected = BufferedRule(Mandate()).select(RANKS, incumbents)
        assert "S75" not in selected and "S60" in selected and len(selected) == 50

    def test_top_edge_is_strict_by_default_and_optional(self):
        incumbents = [f"S{i:02d}" for i in range(9, 59)]           # S09 and S10 climbed into the top 10
        strict = BufferedRule(Mandate()).select(RANKS, incumbents)
        assert all(RANKS[t] > 10 for t in strict)
        tolerant = BufferedRule(Mandate(top_buffer=2)).select(RANKS, incumbents)
        assert {"S09", "S10"} <= set(tolerant) and len(tolerant) == 50

    def test_unranked_incumbent_is_not_retained(self):
        ranks = {t: r for t, r in RANKS.items() if t != "S20"}
        selected = BufferedRule(Mandate()).select(ranks, [f"S{i:02d}" for i in range(11, 61)])
        assert "S20" not in selected and len(selected) == 50

    def test_too_few_eligible_names_is_an_error(self):
        with pytest.raises(InsufficientUniverse):
            StrictRule(Mandate()).select({f"S{i}": i for i in range(1, 30)}, [])


class TestPortfolio:
    def test_drift_keeps_weights_summing_to_one(self):
        weights = equal_weights(["A", "B", "C", "D"])
        returns = {"A": 0.05, "B": -0.02, "C": 0.0}                   # D has no print today
        r = portfolio_return(weights, returns)
        drifted = drift(weights, returns, r)
        assert sum(drifted.values()) == pytest.approx(1.0)
        assert drifted["A"] > drifted["C"] > drifted["B"]

    def test_turnover_splits_into_membership_and_reweight(self):
        drifted = {"A": 0.30, "B": 0.20, "C": 0.50}
        target = {"A": 0.5, "D": 0.5}
        rebalance = Rebalance.between("d", drifted, target)
        assert rebalance.added == ("D",) and rebalance.dropped == ("B", "C")
        assert rebalance.membership_turnover == pytest.approx(0.5 * (0.5 + 0.2 + 0.5))
        assert rebalance.reweight_turnover == pytest.approx(0.5 * 0.2)

    def test_no_membership_change_still_costs_reweighting(self):
        rebalance = Rebalance.between("d", {"A": 0.6, "B": 0.4}, {"A": 0.5, "B": 0.5})
        assert rebalance.membership_turnover == 0 and rebalance.reweight_turnover == pytest.approx(0.1)


def test_reentries_count_round_trips_inside_the_window():
    history = [
        Rebalance("1", (), ("X",), 0, 0),
        Rebalance("2", ("X",), (), 0, 0),        # back after 1 rebalance -> counts
        Rebalance("3", (), ("Y",), 0, 0),
        *[Rebalance(str(i), (), (), 0, 0) for i in range(4, 9)],
        Rebalance("9", ("Y",), (), 0, 0),        # back after 6 rebalances -> outside window 4
    ]
    assert count_reentries(history, window=4) == 1


def test_simulation_never_moves_the_level_on_membership_change():
    tickers = [f"S{i:02d}" for i in range(1, 6)]
    market = MarketData(
        calendar=("d0", "d1", "d2"),
        rebalance_dates=frozenset({"d1"}),
        ranks={"d0": {t: i for i, t in enumerate(tickers, 1)}, "d1": {t: 6 - i for i, t in enumerate(tickers, 1)}},
        returns={"d1": {t: 0.10 for t in tickers}, "d2": {t: 0.0 for t in tickers}},
        universe_size=5,
    )
    history = simulate(market, Mandate(size=2, exclude_top=1, buffer=0), Variant.RAW)
    assert [p.level for p in history.levels] == pytest.approx([1000.0, 1100.0, 1100.0])
    assert history.rebalances[1].added and history.rebalances[1].dropped
