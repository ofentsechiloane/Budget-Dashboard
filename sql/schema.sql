-- Staging: raw landing zone, replaced on every run
CREATE TABLE IF NOT EXISTS stg_transactions (
    run_id        INTEGER,
    source_file   TEXT,
    source_row    INTEGER,
    bank          TEXT,
    account       TEXT,
    raw_date      TEXT,
    raw_amount    TEXT,
    description   TEXT
);

-- Rows that failed validation (idempotent via reject_id)
CREATE TABLE IF NOT EXISTS rejects (
    reject_id     TEXT PRIMARY KEY,
    run_id        INTEGER,
    source_file   TEXT,
    source_row    INTEGER,
    raw_date      TEXT,
    raw_amount    TEXT,
    description   TEXT,
    reason        TEXT
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key      INTEGER PRIMARY KEY,   -- yyyymmdd
    date          TEXT NOT NULL,
    year          INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    month_name    TEXT NOT NULL,
    day           INTEGER NOT NULL,
    weekday       TEXT NOT NULL,
    is_month_end  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_category (
    category_key   INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    type           TEXT NOT NULL CHECK (type IN ('income', 'expense')),
    monthly_budget REAL NOT NULL DEFAULT 0,
    color          TEXT
);

CREATE TABLE IF NOT EXISTS dim_account (
    account_key   INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name  TEXT NOT NULL UNIQUE,
    bank          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_transactions (
    transaction_id TEXT PRIMARY KEY,
    date_key       INTEGER NOT NULL REFERENCES dim_date(date_key),
    category_key   INTEGER NOT NULL REFERENCES dim_category(category_key),
    account_key    INTEGER NOT NULL REFERENCES dim_account(account_key),
    amount_zar     REAL NOT NULL,        -- negative = spend, positive = income
    description    TEXT NOT NULL,
    merchant       TEXT NOT NULL,
    source_file    TEXT NOT NULL,
    loaded_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fact_date     ON fact_transactions(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_category ON fact_transactions(category_key);

-- Run log
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at         TEXT NOT NULL,
    finished_at        TEXT,
    status             TEXT NOT NULL,
    rows_read          INTEGER,
    rows_rejected      INTEGER,
    duplicates_dropped INTEGER,
    rows_inserted      INTEGER,
    error              TEXT
);
