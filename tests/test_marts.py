import json
import sqlite3

import pytest

import generate_sample
import marts
import run_pipeline

TODAY = "2026-10-15"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("built")
    sample = generate_sample.generate(base / "sample", seed=42)
    db, out = base / "w.db", base / "out"
    run_pipeline.run(sample, db, out, today=TODAY)
    return db, out


def test_all_mart_files_are_exported(built):
    _, out = built
    for view in marts.MART_VIEWS:
        assert (out / f"{view}.json").exists(), view
    assert (out / "dashboard.json").exists()


def test_dashboard_json_shape(built):
    _, out = built
    payload = json.loads((out / "dashboard.json").read_text())
    assert {"generated_at", "months", "data"} <= payload.keys()
    assert payload["months"], "no months exported"
    for month in payload["months"]:
        entry = payload["data"][month]
        assert "income" in entry and entry["envelopes"]
        for env in entry["envelopes"]:
            assert {"id", "name", "budget", "color", "transactions"} <= env.keys()


def test_dashboard_spend_reconciles_with_warehouse(built):
    db, out = built
    payload = json.loads((out / "dashboard.json").read_text())
    exported = sum(t["amount"]
                   for m in payload["data"].values()
                   for env in m["envelopes"]
                   for t in env["transactions"])
    conn = sqlite3.connect(db)
    spent = conn.execute(
        "SELECT -SUM(f.amount_zar) FROM fact_transactions f "
        "JOIN dim_category c USING(category_key) WHERE c.type='expense'").fetchone()[0]
    assert exported == pytest.approx(spent, abs=0.01)