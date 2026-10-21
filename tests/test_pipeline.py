import sqlite3

import pandas as pd
import pytest

import extract
import generate_sample
import run_pipeline
import transform
import validate

TODAY = "2026-10-15"


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    return generate_sample.generate(tmp_path_factory.mktemp("sample"), seed=42)


def _row(**kw):
    base = {"source_file": "t.csv", "source_row": 1, "bank": "FNB", "account": "FNB Cheque",
            "raw_date": "2026/09/01", "raw_amount": "-10", "description": "POS PURCHASE SHOPRITE 1234",
            "category_hint": None, "date": pd.Timestamp("2026-09-01"), "amount": -10.0}
    base.update(kw)
    return base


# ---------- validate ----------
@pytest.mark.parametrize("override,reason", [
    ({"description": "   "}, "missing description"),
    ({"date": pd.NaT}, "invalid date"),
    ({"date": pd.Timestamp("2099-01-01")}, "future date"),
    ({"amount": float("nan")}, "invalid amount"),
    ({"amount": 0.0}, "zero amount"),
])
def test_validate_rejects_bad_rows(override, reason):
    df = pd.DataFrame([_row(), _row(**override)])
    valid, rejects = validate.validate(df, today=TODAY)
    assert len(valid) == 1
    assert rejects["reason"].tolist() == [reason]


# ---------- transform ----------
def test_categorise_by_keyword_and_hint():
    assert transform.categorise("POS PURCHASE SHOPRITE 1234", -50) == "Groceries"
    assert transform.categorise("CURRENT ACCOUNT FEE", -5) == "Uncategorised"   # no partial-word match on RENT
    assert transform.categorise("UNKNOWN", 100) == "Other Income"
    assert transform.categorise("Lunch", -50, hint="Eating Out") == "Eating Out"


def test_merchant_cleaning():
    assert transform.merchant_of("POS PURCHASE SHOPRITE 4411") == "Shoprite"


def test_transform_dedupes_and_ids_are_deterministic():
    df = pd.DataFrame([_row(), _row(source_row=2), _row(description="POS PURCHASE UBER TRIP", source_row=3)])
    clean1, dups = transform.transform(df)
    clean2, _ = transform.transform(df)
    assert dups == 1 and len(clean1) == 2
    assert clean1["transaction_id"].tolist() == clean2["transaction_id"].tolist()


# ---------- extract ----------
def test_extract_reads_all_sources(sample):
    raw = extract.read_sources(sample)
    assert set(raw["bank"]) == {"FNB", "Capitec", "Budget Dashboard"}
    assert (raw.loc[raw["bank"] == "Budget Dashboard", "amount"] < 0).all()   # spend stored negative


# ---------- end to end ----------
def test_pipeline_is_idempotent(sample, tmp_path):
    db, out = tmp_path / "w.db", tmp_path / "out"
    first = run_pipeline.run(sample, db, out, today=TODAY)
    second = run_pipeline.run(sample, db, out, today=TODAY)
    assert first["rows_inserted"] > 0 and first["rows_rejected"] == 6
    assert second["rows_inserted"] == 0

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM fact_transactions").fetchone()[0] == first["rows_inserted"]
    assert conn.execute("SELECT COUNT(*) FROM rejects").fetchone()[0] == 6
    assert conn.execute("SELECT COUNT(*) FROM fact_transactions WHERE category_key NOT IN "
                        "(SELECT category_key FROM dim_category)").fetchone()[0] == 0
    assert (out / "dashboard.json").exists()


def test_failed_run_is_logged(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        run_pipeline.run(empty, tmp_path / "w.db", tmp_path / "out", today=TODAY)
    status = sqlite3.connect(tmp_path / "w.db").execute("SELECT status FROM pipeline_runs").fetchone()[0]
    assert status == "failed"
