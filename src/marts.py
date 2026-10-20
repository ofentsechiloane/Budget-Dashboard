"""Build SQL marts and export them as JSON for the dashboard."""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import MARTS

MART_VIEWS = ["mart_monthly_spend", "mart_monthly_income", "mart_budget_vs_actual",
              "mart_top_merchants", "mart_mom_change"]


def build(conn):
    conn.executescript(MARTS.read_text())


def _dashboard_payload(conn):
    months = [r[0] for r in conn.execute(
        """SELECT DISTINCT printf('%04d-%02d', d.year, d.month) m FROM fact_transactions f
           JOIN dim_date d USING(date_key) ORDER BY m""")]
    income = dict(conn.execute("SELECT month_key, income_zar FROM mart_monthly_income"))
    cats = conn.execute(
        "SELECT category_key, name, monthly_budget, color FROM dim_category WHERE type='expense' ORDER BY category_key"
    ).fetchall()
    txns = defaultdict(list)
    for month, ckey, d, desc, amt in conn.execute(
        """SELECT printf('%04d-%02d', d.year, d.month), f.category_key, d.date, f.description, f.amount_zar
           FROM fact_transactions f JOIN dim_date d USING(date_key)
           JOIN dim_category c USING(category_key) WHERE c.type='expense' ORDER BY d.date, f.transaction_id"""):
        txns[(month, ckey)].append({"amount": round(-amt, 2), "note": desc,
                                    "date": datetime.fromisoformat(d).strftime("%d/%m/%Y")})
    data = {}
    for m in months:
        envs = []
        for ckey, name, budget, color in cats:
            t = txns.get((m, ckey), [])
            if budget > 0 or t:
                envs.append({"id": ckey, "name": name, "budget": budget, "color": color, "transactions": t})
        data[m] = {"income": income.get(m, 0), "envelopes": envs}
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "months": months, "data": data}


def export(conn, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for view in MART_VIEWS:
        df = pd.read_sql_query(f"SELECT * FROM {view}", conn)
        (out / f"{view}.json").write_text(df.to_json(orient="records", indent=2))
    (out / "dashboard.json").write_text(json.dumps(_dashboard_payload(conn), indent=2))
    return out
