# Budget Pipeline

A batch data pipeline that turns raw bank-statement exports into a clean, modelled warehouse and serves the results to a budget dashboard.

Built for my Data Engineering elective. It evolves the Budget Dashboard demo from my portfolio into a proper ingest → validate → transform → load → serve pipeline.

---

## WTC-ZJG2A7V6

## Problem statement

My original Budget Dashboard was a front-end demo. All data lived in the browser's LocalStorage, which meant:

- **No source of truth.** Clearing the browser cleared the data.
- **No real data.** Transactions had to be typed in by hand; nothing could be imported from a bank.
- **No validation.** Bad dates, empty amounts and duplicates went straight in.
- **No history or analysis.** There was no way to compare months or see budget vs actual over time.
- **Messy sources.** Real bank exports differ by bank (date formats, signed amounts vs separate In/Out columns), so they cannot be loaded as-is.

## Solution

A pipeline that takes raw files from several sources and produces trustworthy, analysis-ready data:

1. **Extract** transactions from multiple CSV formats and the dashboard's JSON export into one uniform shape.
2. **Validate** every row and quarantine failures in a `rejects` table with a reason, so nothing is silently lost.
3. **Transform**: clean descriptions, extract merchants, auto-categorise, and deduplicate using deterministic IDs.
4. **Load** into a SQLite star schema (one fact table, three dimensions). Loads are idempotent: re-running never creates duplicates.
5. **Model** SQL marts (monthly spend, budget vs actual, top merchants, month-over-month change).
6. **Serve** the marts as JSON, which the dashboard reads instead of LocalStorage.

## Why this approach

| Decision | Reason |
|---|---|
| **Staging before the warehouse** | Raw data is kept exactly as received, so rules can change and data can be reprocessed. |
| **Reject, don't drop** | Bad rows are stored with a reason, so data loss is visible and fixable. |
| **Deterministic transaction IDs** | A hash of date + amount + description + account makes loads idempotent and removes overlap between statements. |
| **Star schema** | Simple joins and fast aggregation for budget analysis. |
| **Plain SQL for marts** | Business logic is readable, testable and portable to Postgres. |
| **Run log (`pipeline_runs`)** | Every run records status and row counts, so failures and data volumes can be audited. |
| **SQLite** | Zero setup, so anyone can clone and run the project in a minute. |

## When to use it

- You get periodic bank statement exports (monthly or weekly) and want one clean history.
- You combine data from more than one bank or account, each with its own format.
- You want repeatable runs: same input, same output, no duplicates.
- You want budget vs actual reporting without manual spreadsheet work.

**Not a fit for:** real-time or streaming data, multi-user production systems, or very large datasets (see Limitations).

---

## Project structure

```
Budget-Dashboard/
├── .github/
│   └── workflows/
│       └── ci.yml          # Tests, pipeline run, idempotency check, Pages deploy
├── data/
│   ├── raw/                # Your real source files (git-ignored)
│   └── sample/             # Synthetic bank exports for demo and tests
├── src/
│   ├── config.py           # Paths, category rules, budgets
│   ├── generate_sample.py  # Synthetic data generator (includes dirty rows)
│   ├── extract.py          # Read CSV / JSON sources into one DataFrame
│   ├── validate.py         # Data quality checks, route bad rows to rejects
│   ├── transform.py        # Clean, categorise, deduplicate
│   ├── load.py             # Idempotent load into the warehouse
│   ├── marts.py            # Build marts and export JSON
│   └── run_pipeline.py     # Runs every stage in order, with logging
├── sql/
│   ├── schema.sql          # Warehouse tables
│   └── marts.sql           # Analytical views
├── dashboard/
│   ├── budget-dashboard.html
│   └── data/               # Pipeline output the dashboard reads (generated, git-ignored)
├── tests/
│   ├── test_pipeline.py    # Validation, transforms, extract, idempotency, failed runs
│   └── test_marts.py       # Mart exports, dashboard JSON shape, spend reconciliation
├── Makefile
├── pytest.ini
├── requirements.txt
└── README.md
```

## How it works

```
Sources             Extract      Staging          Validate        Transform
bank CSVs      ┐                                       │              │
dashboard JSON ┴→ extract.py → stg_transactions → validate.py → transform.py
                                                       │              │
                                                       ↓              ↓
                                                    rejects     clean rows
                                                                      │
                                                                      ↓
                          dashboard JSON ← marts.sql ← warehouse (star schema)
                                 │                        load.py
                                 ↓
                       budget-dashboard.html
```

### 1. Extract (`extract.py`)

Detects each file by its name prefix and parses it into a common set of columns: date, amount, description, account, bank, source file and row number. Sign convention: **negative = spend, positive = income**.

| Source | Format handled |
|---|---|
| FNB CSV | `YYYY/MM/DD`, one signed amount column |
| Capitec CSV | `DD/MM/YYYY`, separate Money In / Money Out columns |
| Dashboard JSON | LocalStorage export, spend stored as positive, category taken from the envelope name |

Unparseable dates and amounts become empty values here. Judging them is the validator's job.

### 2. Stage

The raw extract is written to `stg_transactions` exactly as received (replaced on each run).

### 3. Validate (`validate.py`)

| Check | On failure |
|---|---|
| Description present | Reject: `missing description` |
| Date parses | Reject: `invalid date` |
| Date not in the future | Reject: `future date` |
| Amount is numeric | Reject: `invalid amount` |
| Amount is not zero | Reject: `zero amount` |

Rejected rows go to the `rejects` table with the source file, row number and reason.

### 4. Transform (`transform.py`)

- Collapse whitespace and strip card prefixes (`POS PURCHASE`, `DEBIT ORDER`)
- Extract a clean **merchant** name (`POS PURCHASE SHOPRITE 4411` → `Shoprite`)
- **Categorise** with whole-word keyword matching from `config.py` (the dashboard export's own category wins). Unmatched income becomes `Other Income`; unmatched spend becomes `Uncategorised`.
- Build `transaction_id` = hash of date + amount + description + account
- Drop duplicates by `transaction_id`

### 5. Load (`load.py`)

Upserts dimensions (`dim_date`, `dim_category`, `dim_account`), then inserts facts with `INSERT OR IGNORE`, so a second run inserts 0 rows.

**`fact_transactions`**

| Column | Notes |
|---|---|
| `transaction_id` | Primary key (hash) |
| `date_key`, `category_key`, `account_key` | Foreign keys to the dimensions |
| `amount_zar` | Negative = spend, positive = income |
| `description`, `merchant` | Cleaned text |
| `source_file`, `loaded_at` | Lineage |

### 6. Marts (`marts.sql`, `marts.py`)

| Mart | Answers |
|---|---|
| `mart_monthly_spend` | How much did I spend per category each month? |
| `mart_monthly_income` | What came in each month? |
| `mart_budget_vs_actual` | Budget, actual, variance and % used per category |
| `mart_top_merchants` | Where does my money go? |
| `mart_mom_change` | How did total spend change vs the previous month? |

`marts.py` exports each mart plus a combined `dashboard.json` to `dashboard/data/`.

### 7. Orchestrate (`run_pipeline.py`)

Runs all stages in order, logs counts for rows read, rejected, deduplicated and inserted, and records the run in `pipeline_runs` (success or failed with the error).

---

## Getting started

### macOS / Linux

```bash
git clone https://github.com/ofentsechiloane/Budget-Dashboard.git
cd Budget-Dashboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

```bash
python src/generate_sample.py                  # create demo data
python src/run_pipeline.py --input data/sample # run the pipeline
pytest                                         # run the tests
cd dashboard && python3 -m http.server 8000    # open http://localhost:8000/budget-dashboard.html
```

Makefile shortcuts: `make setup`, `make sample`, `make run`, `make test`, `make serve`.

### Windows (PowerShell)

`make` is usually not installed on Windows, so run the commands directly.

```powershell
git clone https://github.com/ofentsechiloane/Budget-Dashboard.git
cd Budget-Dashboard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```powershell
python src\generate_sample.py                    # create demo data
python src\run_pipeline.py --input data\sample   # run the pipeline
python -m pytest -q                              # run the tests
cd dashboard; python -m http.server 8000         # open http://localhost:8000/budget-dashboard.html
```

If PowerShell blocks `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.

### Options

Flags: `--reset` rebuilds the warehouse from scratch, `--db` sets the warehouse path, `--out` sets the dashboard JSON folder.

To use real statements, put them in `data/raw/` (git-ignored), name them with the bank prefix (`fnb_*.csv`, `capitec_*.csv`) and run with `--input data/raw`.

The dashboard reads `dashboard/data/dashboard.json`, which is generated by the pipeline, so run the pipeline before serving the dashboard locally.

### Scheduling

Run daily at 06:00 with cron:

```cron
0 6 * * * cd /path/to/Budget-Dashboard && .venv/bin/python src/run_pipeline.py --input data/raw >> logs/cron.log 2>&1
```

On Windows, use Task Scheduler to run `.venv\Scripts\python.exe src\run_pipeline.py --input data\raw` from the project folder.

## Testing and CI

`pytest` runs 14 tests covering validation rules, categorisation and merchant cleaning, deterministic IDs and deduplication, source extraction, end-to-end idempotency, failed-run logging, mart exports, the dashboard JSON shape, and a reconciliation check that dashboard spend matches warehouse spend.

GitHub Actions (`.github/workflows/ci.yml`) runs the syntax check and tests, builds the warehouse from sample data, confirms a second run inserts 0 rows, and deploys the dashboard to GitHub Pages from `main`.

## Results on the sample data

| Metric | Value |
|---|---|
| Rows read | 181 |
| Rejected (all failure types covered) | 6 |
| Duplicates dropped | 2 |
| Loaded into the warehouse | 173 |
| Rows inserted on a second run | 0 |

## Limitations and next steps

- Batch only; no streaming ingestion
- Rule-based categorisation (keywords), not ML
- Dedupe by hash means two genuinely identical purchases on the same day collapse into one
- Single user, local SQLite warehouse
- Possible extensions: Postgres, an Airflow DAG, an S3 landing zone, incremental loads with a date watermark

## Data and privacy

Only synthetic data is committed. Real statements belong in `data/raw/`, which is git-ignored.

## Author

**Ofentse Chiloane**, Software Engineering student, WeThinkCode_
[GitHub](https://github.com/ofentsechiloane) · [LinkedIn](https://www.linkedin.com/in/ofentse-chiloane)
