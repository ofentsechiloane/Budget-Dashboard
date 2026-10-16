"""Read raw sources into one uniform DataFrame. No cleaning here, only parsing."""
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from config import SOURCES

log = logging.getLogger(__name__)

COLUMNS = ["source_file", "source_row", "bank", "account", "raw_date", "raw_amount",
           "description", "category_hint", "date", "amount"]


def _read_csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _fnb(path, bank, account):
    df = _read_csv(path)
    return pd.DataFrame({
        "source_row": df.index + 2,
        "raw_date": df["Date"],
        "raw_amount": df["Amount"],
        "description": df["Description"],
        "category_hint": None,
        "date": pd.to_datetime(df["Date"], format="%Y/%m/%d", errors="coerce"),
        "amount": pd.to_numeric(df["Amount"], errors="coerce"),
    })


def _capitec(path, bank, account):
    df = _read_csv(path)
    money_in = pd.to_numeric(df["Money In"], errors="coerce")
    money_out = pd.to_numeric(df["Money Out"], errors="coerce")
    amount = money_in.fillna(0) - money_out.fillna(0)
    amount = amount.where(money_in.notna() | money_out.notna(), np.nan)
    return pd.DataFrame({
        "source_row": df.index + 2,
        "raw_date": df["Transaction Date"],
        "raw_amount": "in=" + df["Money In"] + ";out=" + df["Money Out"],
        "description": df["Transaction Description"],
        "category_hint": None,
        "date": pd.to_datetime(df["Transaction Date"], format="%d/%m/%Y", errors="coerce"),
        "amount": amount,
    })


def _dashboard_export(path, bank, account):
    data = json.loads(Path(path).read_text())
    rows = []
    for env in data.get("envelopes", []):
        for t in env.get("transactions", []):
            rows.append({"raw_date": str(t.get("date", "")), "raw_amount": str(t.get("amount", "")),
                         "description": t.get("note", ""), "category_hint": env.get("name")})
    df = pd.DataFrame(rows, columns=["raw_date", "raw_amount", "description", "category_hint"])
    df.insert(0, "source_row", df.index + 1)
    df["date"] = pd.to_datetime(df["raw_date"], format="%d/%m/%Y", errors="coerce")
    df["amount"] = -pd.to_numeric(df["raw_amount"], errors="coerce")  # export stores spend as positive
    return df


PARSERS = {"fnb": _fnb, "capitec": _capitec, "dashboard_export": _dashboard_export}


def read_sources(input_dir):
    frames = []
    for path in sorted(Path(input_dir).iterdir()):
        if path.suffix.lower() not in (".csv", ".json"):
            continue
        key = next((k for k in SOURCES if path.name.lower().startswith(k)), None)
        if key is None:
            log.warning("Skipping unrecognised file: %s", path.name)
            continue
        bank, account = SOURCES[key]
        df = PARSERS[key](path, bank, account)
        df["source_file"], df["bank"], df["account"] = path.name, bank, account
        log.info("Extracted %d rows from %s", len(df), path.name)
        frames.append(df[COLUMNS])
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    return pd.concat(frames, ignore_index=True)
