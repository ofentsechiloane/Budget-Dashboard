"""Warehouse loading. Every write is idempotent: re-running never duplicates rows."""
import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

from config import CATEGORIES, SCHEMA


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text())
    return conn


def start_run(conn):
    with conn:
        cur = conn.execute("INSERT INTO pipeline_runs (started_at, status) VALUES (?, 'running')", (_now(),))
    return cur.lastrowid


def finish_run(conn, run_id, status, rows_read=None, rows_rejected=None,
               duplicates_dropped=None, rows_inserted=None, error=None):
    with conn:
        conn.execute(
            """UPDATE pipeline_runs SET finished_at=?, status=?, rows_read=?, rows_rejected=?,
               duplicates_dropped=?, rows_inserted=?, error=? WHERE run_id=?""",
            (_now(), status, rows_read, rows_rejected, duplicates_dropped, rows_inserted, error, run_id))


def stage(conn, raw, run_id):
    """Replace the staging table with the raw extract, exactly as received."""
    rows = [(run_id, r.source_file, int(r.source_row), r.bank, r.account,
             r.raw_date, r.raw_amount, r.description) for r in raw.itertuples()]
    with conn:
        conn.execute("DELETE FROM stg_transactions")
        conn.executemany("INSERT INTO stg_transactions VALUES (?,?,?,?,?,?,?,?)", rows)


def load_rejects(conn, rejects, run_id):
    rows = []
    for r in rejects.itertuples():
        rid = hashlib.sha1(f"{r.source_file}|{r.source_row}|{r.reason}".encode()).hexdigest()[:16]
        rows.append((rid, run_id, r.source_file, int(r.source_row), r.raw_date, r.raw_amount,
                     r.description, r.reason))
    with conn:
        conn.executemany("INSERT OR IGNORE INTO rejects VALUES (?,?,?,?,?,?,?,?)", rows)


def _upsert_dims(conn, clean):
    for name, cfg in CATEGORIES.items():
        conn.execute(
            """INSERT INTO dim_category (name, type, monthly_budget, color) VALUES (?,?,?,?)
               ON CONFLICT(name) DO UPDATE SET type=excluded.type,
               monthly_budget=excluded.monthly_budget, color=excluded.color""",
            (name, cfg["type"], cfg["budget"], cfg["color"]))
    for acc, bank in clean[["account", "bank"]].drop_duplicates().itertuples(index=False):
        conn.execute("INSERT OR IGNORE INTO dim_account (account_name, bank) VALUES (?,?)", (acc, bank))
    for d in clean["date"].drop_duplicates():
        d = d.date()
        month_end = int((d + timedelta(days=1)).day == 1)
        conn.execute("INSERT OR IGNORE INTO dim_date VALUES (?,?,?,?,?,?,?,?)",
                     (int(d.strftime("%Y%m%d")), d.isoformat(), d.year, d.month,
                      d.strftime("%B"), d.day, d.strftime("%A"), month_end))


def load_warehouse(conn, clean):
    """Insert facts; returns the number of NEW rows (0 on a clean re-run)."""
    loaded_at = _now()
    with conn:
        _upsert_dims(conn, clean)
        cat = dict(conn.execute("SELECT name, category_key FROM dim_category"))
        acc = dict(conn.execute("SELECT account_name, account_key FROM dim_account"))
        rows = [(r.transaction_id, int(r.date.strftime("%Y%m%d")), cat[r.category], acc[r.account],
                 float(r.amount), r.description, r.merchant, r.source_file, loaded_at)
                for r in clean.itertuples()]
        before = conn.total_changes
        conn.executemany("INSERT OR IGNORE INTO fact_transactions VALUES (?,?,?,?,?,?,?,?,?)", rows)
        return conn.total_changes - before
