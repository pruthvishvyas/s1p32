import numpy as np
import pandas as pd

from config import settings as S
from src.data import loading
from src.utils import paths
from src.utils.columns import has
from src.utils.io_utils import save_csv, save_json

C = S.COL


def _to_number(s):
    if s.dtype == object:
        s = s.astype(str).str.replace(r"[^0-9eE.+-]", "", regex=True).replace("", np.nan)
    return pd.to_numeric(s, errors="coerce")


def clean(verbose=True):
    df, absent = loading.load_raw()
    raw_rows = len(df)
    log = {"raw_rows": int(raw_rows), "removed": {}, "capped": {}, "absent_optional": absent}
    pii = [c for c in loading.pii_columns(df) if c not in C.values()]
    if pii:
        df = df.drop(columns=pii)
        log["personal_columns_dropped"] = pii
    for key in S.TEXT_KEYS:
        if has(df, key):
            df[C[key]] = df[C[key]].astype(str).str.strip().replace({"nan": np.nan, "": np.nan})
    for key in S.CAT_CASE_KEYS:
        if has(df, key):
            s = df[C[key]]
            nn = s.dropna()
            canon = nn.groupby(nn.str.lower()).agg(lambda v: v.value_counts().index[0])
            df[C[key]] = s.str.lower().map(canon)
    for key in S.NUMERIC_KEYS:
        if has(df, key):
            df[C[key]] = _to_number(df[C[key]])
    d = pd.to_datetime(df[C["date"]], errors="coerce")
    log["date_failures"] = int(d.isna().sum())
    df[C["date"]] = d

    def drop(mask, label):
        nonlocal df
        n = int((~mask).sum())
        log["removed"][label] = n
        df = df[mask]
        if verbose:
            print("removed", n, "rows:", label)

    drop(df[C["batch"]].notna(), "no batch id")
    drop(~df.duplicated(subset=[C["batch"]], keep="first"), "duplicate batch id")
    drop(df[C["revenue"]].notna() & (df[C["revenue"]] > 0), "missing or non-positive revenue")
    neg = 0
    for key in S.NONNEG_KEYS:
        if has(df, key):
            m = df[C[key]] < 0
            neg += int(m.sum())
            df.loc[m, C[key]] = np.nan
    log["negative_values_blanked"] = neg
    for key in S.CAP_KEYS:
        if not has(df, key):
            continue
        s = df[C[key]]
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if not np.isfinite(iqr) or iqr == 0:
            continue
        lo, hi = q1 - S.IQR_CAP_FACTOR * iqr, q3 + S.IQR_CAP_FACTOR * iqr
        before = int(((s < lo) | (s > hi)).sum())
        df[C[key]] = s.clip(lo, hi)
        after = int(((df[C[key]] < lo) | (df[C[key]] > hi)).sum())
        log["capped"][C[key]] = {"outliers_before": before, "outliers_after": after}
        if verbose:
            print("outlier cap", C[key], "before", before, "after", after)
    df = df.reset_index(drop=True)
    log["clean_rows"] = int(len(df))
    log["removed_share_pct"] = round(100.0 * (raw_rows - len(df)) / (raw_rows if raw_rows else 1), 2)
    save_csv(df, paths.P["clean"])
    save_json(log, paths.P["cleaning_log"])
    if verbose:
        print("clean rows", len(df), "of", raw_rows)
    return log
