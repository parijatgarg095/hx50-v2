"""HTTP contract tests against a synthetic build."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hx50.api import create_app
from hx50.config import Settings
from hx50.domain import Mandate
from hx50.pipeline.build import build_index

from conftest import sources_in
from synthetic import HOLIDAY, LAST_BEFORE_HOLIDAY

REBALANCE_MONDAY = "2026-01-12"
MID_WEEK = "2026-01-14"


@pytest.fixture()
def client(tmp_path, market) -> TestClient:
    directory = market.write(tmp_path)
    build_index(sources_in(directory), Mandate(), directory / "hx50.db")
    return TestClient(create_app(Settings(data_dir=directory, db_path=directory / "hx50.db")))


def test_levels_start_at_base(client):
    levels = client.get("/api/levels", params={"start": "2026-01-05", "end": "2026-02-27"}).json()
    assert levels[0]["level"] == 1000.0 and levels[0]["cumulative_return"] == 0
    assert {"date", "level", "daily_return", "cumulative_return", "rebalanced"} <= set(levels[0])


def test_composition_is_equal_on_rebalance_and_drifted_mid_week(client):
    rebalance = client.get("/api/composition", params={"date": REBALANCE_MONDAY}).json()
    mid_week = client.get("/api/composition", params={"date": MID_WEEK}).json()
    assert rebalance["rebalance_day"]
    assert [h["weight"] for h in rebalance["holdings"]] == pytest.approx([0.02] * 50)
    assert not mid_week["rebalance_day"] and mid_week["last_rebalance"] == REBALANCE_MONDAY
    assert len({h["weight"] for h in mid_week["holdings"]}) > 10
    assert mid_week["weight_sum"] == pytest.approx(1) and mid_week["count"] == 50


def test_composition_edge_cases(client):
    assert client.get("/api/composition", params={"date": HOLIDAY}).json()["as_of"] == LAST_BEFORE_HOLIDAY
    assert client.get("/api/composition", params={"date": "2020-01-01"}).status_code == 404
    assert client.get("/api/composition", params={"date": "garbage"}).status_code == 422
    assert client.get("/api/levels", params={"variant": "nope"}).status_code == 422
    assert client.get("/api/levels", params={"start": "2026-03-01", "end": "2026-02-01"}).status_code == 422


def test_rebalances_and_scorecard(client):
    rebalances = client.get("/api/rebalances").json()
    assert rebalances[0]["initial"] and all("turnover" in r for r in rebalances)
    cards = {c["variant"]: c for c in client.get("/api/scorecard").json()}
    assert cards["stabilised"]["total_turnover"] < cards["raw"]["total_turnover"]


def test_run_exposes_mandate_and_provenance(client):
    run = client.get("/api/run").json()
    assert run["mandate"]["first_rank"] == 11 and run["mandate"]["retention_floor"] == 70
    assert len(run["run_id"]) == 12 and len(run["data_sha256"]) == 64


def test_rebuild_changes_mandate_and_rejects_impossible_one(client):
    response = client.post("/api/rebuild", json={"size": 30, "exclude_top": 20, "buffer": 5, "top_buffer": 0})
    assert response.status_code == 200 and response.json()["run"]["mandate"]["size"] == 30
    assert client.get("/api/composition", params={"date": "2026-03-02"}).json()["count"] == 30

    rejected = client.post("/api/rebuild", json={"size": 500, "exclude_top": 10, "buffer": 5, "top_buffer": 0})
    assert rejected.status_code == 422
    assert client.get("/api/composition", params={"date": "2026-03-02"}).json()["count"] == 30


def test_unbuilt_index_returns_503(tmp_path):
    client = TestClient(create_app(Settings(data_dir=tmp_path, db_path=tmp_path / "missing.db")))
    response = client.get("/api/run")
    assert response.status_code == 503 and "hx50 build" in response.json()["detail"]


def test_dashboard_is_served(client):
    page = client.get("/")
    assert page.status_code == 200 and "HX-50" in page.text
    assert client.get("/assets/js/main.js").status_code == 200
