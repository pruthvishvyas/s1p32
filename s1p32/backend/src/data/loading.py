import re

import numpy as np
import pandas as pd

from config import settings as S
from src.utils import paths
from src.utils.columns import dates, has, resolve_columns
from src.utils.io_utils import read_table, save_json

C = S.COL
PII_HEADER = re.compile(r"(e[-_ ]?mail|phone|mobile|ssn|dob|birth|address|first[-_ ]?name|last[-_ ]?name|full[-_ ]?name|^name$|ip[-_ ]?addr)", re.I)
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"^\+?\d[\d\s().-]{8,}\d$")
DATE_LIKE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")


def load_raw():
    return resolve_columns(read_table(paths.P["raw"]))


def pii_columns(df):
    found = []
    for c in df.columns:
        if PII_HEADER.search(str(c)):
            found.append(c)
            continue
        if df[c].dtype == object:
            sample = df[c].dropna().astype(str).head(200)
            if sample.empty:
                continue
            hit = sample.map(lambda v: bool(EMAIL.search(v)) or (bool(PHONE.match(v)) and not DATE_LIKE.match(v)))
            if hit.mean() > 0.5:
                found.append(c)
    return found


def validate(verbose=True):
    df, absent = load_raw()
    rep = {"rows": int(len(df)), "cols": int(df.shape[1]), "absent_optional": absent, "schema_ok": True}
    nulls = df.isna().sum()
    nulls = nulls[nulls > 0]
    rep["nulls"] = {k: int(v) for k, v in nulls.items()}
    rep["pii_columns"] = pii_columns(df)
    num = lambda k: pd.to_numeric(df[C[k]], errors="coerce")
    issues = {}
    for k in S.NONNEG_KEYS:
        if has(df, k):
            issues["negative_" + C[k]] = int((num(k) < 0).sum())
    if has(df, "shipped", "size"):
        issues["shipped_above_batch_size"] = int((num("shipped") > num("size")).sum())
    if has(df, "defects", "crit", "major", "minor"):
        issues["severity_sum_differs_from_defects"] = int(((num("crit") + num("major") + num("minor")) != num("defects")).sum())
    if has(df, "copq", "prev", "appr", "int_fail", "ext_fail"):
        gap = (num("copq") - (num("prev") + num("appr") + num("int_fail") + num("ext_fail"))).abs()
        issues["copq_not_matching_components"] = int((gap > 1).sum())
    d = dates(df)
    rep["date_failures"] = int(d.isna().sum())
    rep["date_range"] = {"start": str(d.min().date()) if d.notna().any() else None,
                         "end": str(d.max().date()) if d.notna().any() else None}
    rep["issues"] = {k: v for k, v in issues.items() if v}
    cp = num("copq_pct")
    rep["high_cost_share_pct"] = round(float((cp >= cp.quantile(S.HIGH_COPQ_QUANTILE)).mean() * 100), 2)
    if has(df, "inspection"):
        rep["inspection_result_counts"] = df[C["inspection"]].value_counts().to_dict()
    save_json(rep, paths.P["validation"])
    if verbose:
        print("rows", rep["rows"], "cols", rep["cols"], "date range", rep["date_range"])
        print("columns with nulls:", rep["nulls"] or "none")
        print("rule checks with findings:", rep["issues"] or "none")
        for k in ("plant", "family", "inspection"):
            if has(df, k):
                print(df[C[k]].value_counts().to_string())
    return rep
