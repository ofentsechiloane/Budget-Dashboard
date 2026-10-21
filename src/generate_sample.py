"""Generate synthetic bank exports (with deliberate dirty rows) for demo and tests."""
import argparse
import csv
import json
import random
from datetime import date
from pathlib import Path

from config import SAMPLE_DIR

MONTHS = [(2026, m) for m in range(4, 10)]  # Apr-Sep 2026

GROCERIES = ["Shoprite", "Checkers Hyper", "Pick n Pay", "Spar"]
TRANSPORT = ["Uber Trip", "Bolt Ride", "Engen Garage", "Gautrain"]
EATING = ["KFC", "Nandos", "Steers", "Mugg & Bean"]
HEALTH = ["Dis-Chem", "Clicks"]
SUBS = [("Netflix", 199.00), ("Spotify", 59.99), ("Showmax", 99.00)]


def _spend(rng, merchants, lo, hi, year, month, n, prefix="POS PURCHASE "):
    rows = []
    for _ in range(n):
        d = date(year, month, rng.randint(1, 28))
        ref = f" {rng.randint(1000, 9999)}" if rng.random() < 0.6 else ""
        desc = f"{prefix}{rng.choice(merchants).upper()}{ref}"
        rows.append((d, desc, -round(rng.uniform(lo, hi), 2)))
    return rows


def generate(out_dir=SAMPLE_DIR, seed=42):
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fnb, cap = [], []

    for y, m in MONTHS:
        fnb.append((date(y, m, 25), "SALARY ACME PAYROLL", 18500.00))
        fnb.append((date(y, m, 1), "DEBIT ORDER RENT", -4500.00))
        fnb.append((date(y, m, 5), f"CITY POWER PREPAID {rng.randint(10000, 99999)}", -round(rng.uniform(380, 520), 2)))
        fnb.append((date(y, m, 7), "TELKOM FIBRE", -699.00))
        fnb.append((date(y, m, 10), "VODACOM AIRTIME", -round(rng.uniform(100, 180), 2)))
        for name, amt in SUBS:
            fnb.append((date(y, m, rng.randint(2, 4)), f"DEBIT ORDER {name.upper()}", -amt))

        cap += _spend(rng, GROCERIES, 150, 650, y, m, rng.randint(5, 7))
        cap += _spend(rng, TRANSPORT, 40, 380, y, m, rng.randint(5, 8))
        cap += _spend(rng, EATING, 60, 220, y, m, rng.randint(3, 5))
        cap += _spend(rng, HEALTH, 80, 260, y, m, rng.randint(0, 2))
        cap.append((date(y, m, 28), "INTEREST CAPITALISED", round(rng.uniform(12, 45), 2)))
        if rng.random() < 0.4:
            cap.append((date(y, m, rng.randint(1, 28)), "CASHSEND RECEIVED FROM FRIEND", round(rng.uniform(100, 500), 2)))
        if rng.random() < 0.5:
            cap.append((date(y, m, rng.randint(1, 28)), "POS PURCHASE UNKNOWN MERCHANT XYZ", -round(rng.uniform(50, 300), 2)))

    fnb.sort()
    cap.sort()

    # --- FNB: Date (YYYY/MM/DD), Amount (signed), Balance, Description
    fnb_rows, bal = [], 8000.0
    for d, desc, amt in fnb:
        bal += amt
        fnb_rows.append([d.strftime("%Y/%m/%d"), f"{amt:.2f}", f"{bal:.2f}", desc])
    fnb_rows.append(list(fnb_rows[10]))                                   # exact duplicate
    fnb_rows.append(["2026/06/15", "", "0.00", "POS PURCHASE MYSTERY"])   # missing amount
    fnb_rows.append(["2099/01/01", "-120.00", "0.00", "POS PURCHASE FUTURE SHOP"])  # future date
    fnb_rows.append(["not a date", "-55.00", "0.00", "POS PURCHASE BAD DATE"])      # invalid date
    fnb_rows.append(["2026/07/09", "-80.00", "0.00", "   "])             # missing description
    fnb_rows.append(["2026/08/09", "0.00", "0.00", "POS PURCHASE ZERO"])  # zero amount
    fnb_rows.append(["2026/08/12", "-210.40", "0.00", "pos purchase   shoprite   4411"])  # messy text

    with open(out / "fnb_cheque.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Amount", "Balance", "Description"])
        w.writerows(fnb_rows)

    # --- Capitec: Transaction Date (DD/MM/YYYY), Description, Money In, Money Out
    cap_rows = []
    for d, desc, amt in cap:
        cap_rows.append([d.strftime("%d/%m/%Y"), desc, f"{amt:.2f}" if amt > 0 else "", f"{-amt:.2f}" if amt < 0 else ""])
    cap_rows.append(list(cap_rows[5]))                                    # exact duplicate
    cap_rows.append(["14/07/2026", "POS PURCHASE BLANK AMOUNTS", "", ""])  # both amounts blank

    with open(out / "capitec_savings.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Transaction Date", "Transaction Description", "Money In", "Money Out"])
        w.writerows(cap_rows)

    # --- Budget dashboard JSON export (old LocalStorage shape)
    export = {
        "income": 18500,
        "envelopes": [
            {"name": "Groceries", "budget": 2200, "color": "#534AB7", "transactions": [
                {"amount": 312.5, "note": "Weekend shop", "date": "03/09/2026"},
                {"amount": 148.9, "note": "Top-up", "date": "11/09/2026"}]},
            {"name": "Transport", "budget": 1200, "color": "#185FA5", "transactions": [
                {"amount": 95.0, "note": "Taxi fare", "date": "08/09/2026"}]},
            {"name": "Eating Out", "budget": 600, "color": "#378ADD", "transactions": [
                {"amount": 120.0, "note": "Lunch", "date": "14/09/2026"}]},
        ],
    }
    (out / "dashboard_export.json").write_text(json.dumps(export, indent=2))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(SAMPLE_DIR))
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    print(f"Sample data written to {generate(a.out, a.seed)}")
