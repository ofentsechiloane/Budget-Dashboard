"""Clean, categorise and deduplicate validated rows."""
import hashlib
import re

import pandas as pd

from config import CATEGORIES, OTHER_INCOME, UNCATEGORISED

_PREFIX = re.compile(r"^(POS PURCHASE|DEBIT ORDER|CARD PURCHASE|EFT|PAYMENT)\s+", re.I)
_REF_TAIL = re.compile(r"\s+[#*]?\d{3,}.*$")
_PATTERNS = [
    (name, [re.compile(rf"\b{re.escape(k)}\b") for k in cfg["keywords"]])
    for name, cfg in CATEGORIES.items()
]


def clean_description(s):
    return re.sub(r"\s+", " ", str(s)).strip()


def merchant_of(desc):
    return _REF_TAIL.sub("", _PREFIX.sub("", desc)).strip().title()


def categorise(desc, amount, hint=None):
    if hint in CATEGORIES:
        return hint
    up = desc.upper()
    for name, pats in _PATTERNS:
        if any(p.search(up) for p in pats):
            return name
    return OTHER_INCOME if amount > 0 else UNCATEGORISED


def make_id(date, amount, desc, account):
    key = f"{date:%Y-%m-%d}|{amount:.2f}|{desc.upper()}|{account}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def transform(valid):
    """Returns (clean_df, duplicates_dropped)."""
    df = valid.copy()
    df["description"] = df["description"].map(clean_description)
    df["amount"] = df["amount"].astype(float).round(2)
    df["merchant"] = df["description"].map(merchant_of)
    df["category"] = [categorise(d, a, h) for d, a, h in zip(df["description"], df["amount"], df["category_hint"])]
    df["transaction_id"] = [make_id(d, a, s, acc) for d, a, s, acc in
                            zip(df["date"], df["amount"], df["description"], df["account"])]
    before = len(df)
    df = df.drop_duplicates(subset="transaction_id", keep="first")
    cols = ["transaction_id", "date", "amount", "description", "merchant", "category",
            "account", "bank", "source_file"]
    return df[cols].sort_values(["date", "transaction_id"]).reset_index(drop=True), before - len(df)
