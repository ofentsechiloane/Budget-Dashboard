"""Data quality checks. Failing rows are quarantined with a reason, never silently dropped."""
from datetime import date

import pandas as pd


def validate(df, today=None):
    today = pd.Timestamp(today or date.today())
    desc = df["description"].fillna("").astype(str).str.strip()
    checks = [  # first failing check wins
        ("missing description", desc.eq("")),
        ("invalid date", df["date"].isna()),
        ("future date", df["date"].gt(today)),
        ("invalid amount", df["amount"].isna()),
        ("zero amount", df["amount"].eq(0)),
    ]
    reason = pd.Series("", index=df.index, dtype=object)
    for msg, mask in reversed(checks):
        reason = reason.mask(mask, msg)
    bad = reason.ne("")
    rejects = df[bad].assign(reason=reason[bad])
    return df[~bad].copy(), rejects
