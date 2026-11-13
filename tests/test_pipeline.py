"""End-to-end properties of a build on the synthetic market."""
from __future__ import annotations

import hashlib
import sqlite3

import pandas as pd
import pytest

from hx50.domain import InvalidMandate, Mandate, Variant
from hx50.pipeline.build import build_index
from hx50.pipeline.share_classes import secondary_share_classes

from conftest import sources_in
from synthetic import FIRST_AFTER_HOLIDAY, HOLIDAY, LAST_BEFORE_HOLIDAY, make_market

VARIANTS = list(Variant)


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_close_holds_size_names_summing_to_one(built, variant):
    rows = built.sql("SELECT COUNT(*), SUM(weight) FROM holding WHERE variant = ? GROUP BY date", (variant.value,))
    assert all(count == built.mandate.size and abs(total - 1) < 1e-9 for count, total in rows)


def test_no_excluded_top_name_is_ever_selected(built):
    rebalance_dates = set(built.rebalance_dates())
    ranks = [rank for date, rank in built.sql("SELECT date, market_cap_rank FROM holding") if date in rebalance_dates and rank]
    assert min(ranks) > built.mandate.exclude_top


def test_unstabilised_is_exactly_the_entry_band_on_every_rebalance(built):
    m = built.mandate
    for date in built.rebalance_dates():
        held = {t for (t,) in built.sql("SELECT ticker FROM holding WHERE variant = 'raw' AND date = ?", (date,))}
        band = {t for (t,) in built.sql("SELECT ticker FROM ranked WHERE date = ? AND rank BETWEEN ? AND ?",
                                        (date, m.first_rank, m.last_rank))}
        assert held == band, date


def test_stabilised_members_never_fall_below_the_retention_floor(built):
    rebalance_dates = set(built.rebalance_dates())
    ranks = [rank for date, rank in built.sql("SELECT date, market_cap_rank FROM holding WHERE variant = 'stabilised'")
             if date in rebalance_dates and rank]
    assert max(ranks) <= built.mandate.retention_floor


def test_rebalances_on_first_trading_day_of_each_week(built):
    dates = built.rebalance_dates()
    assert HOLIDAY not in dates and FIRST_AFTER_HOLIDAY in dates
    weeks = pd.to_datetime(pd.Series(dates)).dt.isocalendar()
    assert not weeks[["year", "week"]].duplicated().any()


@pytest.mark.parametrize("variant", VARIANTS)
def test_level_matches_an_independent_units_based_recomputation(built, variant):
    """Buy equal dollar amounts at each rebalance, mark units to market daily: must equal the engine's level."""
    prices = built.market.price_matrix()
    rebalance_dates = set(built.rebalance_dates())
    members = pd.DataFrame(built.sql("SELECT date, ticker FROM holding WHERE variant = ?", (variant.value,)),
                           columns=["date", "ticker"]).groupby("date")["ticker"].apply(list)
    levels = dict(built.sql("SELECT date, level FROM index_level WHERE variant = ?", (variant.value,)))

    units: dict[str, float] = {}
    level = built.mandate.base_level
    for i, date in enumerate(built.calendar()):
        if units:
            level = sum(u * prices.at[date, t] for t, u in units.items())
        if i == 0 or date in rebalance_dates:
            units = {t: (level / built.mandate.size) / prices.at[date, t] for t in members[date]}
        assert level == pytest.approx(levels[date], rel=1e-9), date


def test_weights_drift_between_rebalances_and_reset_on_them(built):
    rebalance_dates = set(built.rebalance_dates())
    spread = dict(built.sql(
        "SELECT date, MAX(weight) - MIN(weight) FROM holding WHERE variant = 'stabilised' GROUP BY date"))
    for i, date in enumerate(built.calendar()):
        if i == 0 or date in rebalance_dates:
            assert spread[date] < 1e-12, date
        else:
            assert spread[date] > 1e-6, date


def test_turnover_parts_add_up_and_quiet_weeks_are_pure_reweight(built):
    for rebalance in built.reader.rebalances(Variant.STABILISED):
        assert 0 <= rebalance.turnover <= 1
        if not rebalance.initial and not rebalance.added:
            assert rebalance.membership_turnover == 0 and rebalance.reweight_turnover > 0


def test_stabilisation_reduces_churn(built):
    cards = {s.variant: s for s in built.reader.scorecards()}
    stabilised, raw = cards[Variant.STABILISED], cards[Variant.RAW]
    assert stabilised.total_turnover < raw.total_turnover
    assert stabilised.names_added < raw.names_added
    assert stabilised.cost_drag == pytest.approx(2 * stabilised.total_turnover * built.mandate.cost_bps / 10_000)


def test_mandate_is_live(build):
    smaller = build(Mandate(size=30, exclude_top=20, buffer=5))
    counts = {count for (count,) in smaller.sql("SELECT COUNT(*) FROM holding GROUP BY variant, date")}
    assert counts == {30}


def test_reader_resolves_non_trading_dates_and_rejects_dates_before_start(built):
    composition = built.reader.composition(Variant.STABILISED, HOLIDAY)
    assert composition.as_of == LAST_BEFORE_HOLIDAY and composition.count == built.mandate.size
    assert built.reader.composition(Variant.STABILISED, "2025-01-01") is None


def test_rebuild_is_deterministic_and_failure_keeps_previous_database(tmp_path):
    market = make_market()
    directory = market.write(tmp_path)
    sources, db = sources_in(directory), directory / "hx50.db"
    first, _ = build_index(sources, Mandate(), db)
    levels = sqlite3.connect(db).execute("SELECT level FROM index_level ORDER BY variant, date").fetchall()
    second, _ = build_index(sources, Mandate(), db)
    assert second.run_id == first.run_id
    assert sqlite3.connect(db).execute("SELECT level FROM index_level ORDER BY variant, date").fetchall() == levels

    fingerprint = hashlib.sha256(db.read_bytes()).hexdigest()
    with pytest.raises(InvalidMandate):
        build_index(sources, Mandate(size=500), db)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == fingerprint
    assert not db.with_name(db.name + ".building").exists()

    market.prices.loc[0, "close"] *= 1.01
    market.write(directory)
    corrected, _ = build_index(sources, Mandate(), db)
    assert corrected.run_id != first.run_id


def test_split_restated_history_leaves_the_index_unchanged(tmp_path):
    """2:1 split: the vendor halves all historical prices and doubles the current share count."""
    original = make_market()
    split = make_market()
    is_t030 = split.prices.ticker == "T030"
    split.prices.loc[is_t030, ["close", "adj_close"]] /= 2
    split.shares.loc[split.shares.ticker == "T030", "shares"] *= 2

    levels = []
    for name, market in (("a", original), ("b", split)):
        directory = market.write(tmp_path / name)
        build_index(sources_in(directory), Mandate(), directory / "hx50.db")
        levels.append([lv for (lv,) in sqlite3.connect(directory / "hx50.db").execute(
            "SELECT level FROM index_level ORDER BY variant, date")])
    assert levels[0] == pytest.approx(levels[1], rel=1e-9)


def test_secondary_share_classes_are_never_ranked_or_held(tmp_path):
    market = make_market()
    largest = market.shares.sort_values("shares").iloc[-1]["ticker"]
    for primary, secondary in (("T040", "T040B"), (largest, f"{largest}B")):
        twin = market.prices[market.prices.ticker == primary].copy()
        twin["ticker"] = secondary
        twin[["close", "adj_close"]] *= 0.99
        market.prices = pd.concat([market.prices, twin], ignore_index=True)
        count = market.shares.loc[market.shares.ticker == primary, "shares"].iloc[0]
        market.shares = pd.concat([market.shares, pd.DataFrame({"ticker": [secondary], "shares": [count]})])

    excluded = secondary_share_classes(market.shares, market.prices)
    assert set(excluded.ticker) == {"T040B", f"{largest}B"}

    directory = market.write(tmp_path, excluded)
    build_index(sources_in(directory), Mandate(), directory / "hx50.db")
    con = sqlite3.connect(directory / "hx50.db")
    secondaries = ("T040B", f"{largest}B")
    assert con.execute("SELECT COUNT(*) FROM ranked WHERE ticker IN (?, ?)", secondaries).fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM holding WHERE ticker IN (?, ?)", secondaries).fetchone()[0] == 0
