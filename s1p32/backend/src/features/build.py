import numpy as np
import pandas as pd

from config import settings as S
from src.utils import paths
from src.utils.columns import has
from src.utils.io_utils import load_required, save_csv, save_json

C = S.COL


def _ratio(a, b, scale=1.0):
    return a / b.replace(0, 1) * scale


def build(verbose=True):
    df = load_required(paths.P["clean"], "cleaning")
    df[C["date"]] = pd.to_datetime(df[C["date"]], errors="coerce")
    new = []

    def add(name, series):
        df[name] = series
        new.append(name)

    if has(df, "defects", "size"):
        add("batch_defect_rate_pct", _ratio(df[C["defects"]], df[C["size"]], 100))
    if has(df, "scrap_u", "size"):
        add("scrap_rate_pct", _ratio(df[C["scrap_u"]], df[C["size"]], 100))
    if has(df, "rework_u", "size"):
        add("rework_rate_pct", _ratio(df[C["rework_u"]], df[C["size"]], 100))
    if has(df, "shipped", "size"):
        add("shipped_yield_pct", _ratio(df[C["shipped"]], df[C["size"]], 100))
    if has(df, "escaped", "shipped"):
        add("escape_rate_per_1000", _ratio(df[C["escaped"]], df[C["shipped"]], 1000))
    if has(df, "crit", "defects"):
        add("critical_share_pct", _ratio(df[C["crit"]], df[C["defects"]], 100))
    if has(df, "crit", "major", "minor", "size"):
        # critical defects weigh ten times a minor one, major three times
        add("severity_index", _ratio(10 * df[C["crit"]] + 3 * df[C["major"]] + df[C["minor"]], df[C["size"]], 1000))
    if "batch_defect_rate_pct" in df and has(df, "sample_rate"):
        add("inspection_gap_pct", df[C["sample_rate"]] - df["batch_defect_rate_pct"])
    if has(df, "prev", "appr", "int_fail", "ext_fail"):
        total = df[C["prev"]] + df[C["appr"]] + df[C["int_fail"]] + df[C["ext_fail"]]
        add("prevention_share_pct", (df[C["prev"]] + df[C["appr"]]) / total.replace(0, 1) * 100)
    if has(df, "ext_fail", "copq"):
        add("external_share_pct", _ratio(df[C["ext_fail"]], df[C["copq"]], 100))
    if has(df, "copq", "shipped"):
        add("cost_per_unit_shipped", _ratio(df[C["copq"]], df[C["shipped"]]))
    if has(df, "price", "unit_cost"):
        add("unit_margin_pct", _ratio(df[C["price"]] - df[C["unit_cost"]], df[C["price"]], 100))
    if has(df, "cpk"):
        add("cpk_band", pd.cut(df[C["cpk"]], [-np.inf, 1.0, 1.33, 1.67, np.inf],
                               labels=["below 1.00", "1.00 to 1.33", "1.33 to 1.67", "1.67 and above"]).astype(object))
    if has(df, "age"):
        add("machine_age_band", pd.cut(df[C["age"]], [-np.inf, 5, 10, 15, np.inf],
                                       labels=["up to 5 years", "6 to 10 years", "11 to 15 years", "over 15 years"]).astype(object))
    d = df[C["date"]]
    add("month_num", d.dt.month)
    add("week_start", (d - pd.to_timedelta(d.dt.weekday, unit="D")).dt.normalize())
    thr = float(df[C["copq_pct"]].quantile(S.HIGH_COPQ_QUANTILE))
    add("high_copq_flag", (df[C["copq_pct"]] >= thr).astype(int))
    save_json({"quantile": S.HIGH_COPQ_QUANTILE, "threshold": thr, "column": C["copq_pct"]}, paths.P["target_info"])
    # position of the batch against all others, higher means more quality risk
    parts = []
    if has(df, "cpk"):
        parts.append((1 - df[C["cpk"]].rank(pct=True), 0.30))
    if "severity_index" in df:
        parts.append((df["severity_index"].rank(pct=True), 0.25))
    if "escape_rate_per_1000" in df:
        parts.append((df["escape_rate_per_1000"].rank(pct=True), 0.20))
    if "batch_defect_rate_pct" in df:
        parts.append((df["batch_defect_rate_pct"].rank(pct=True), 0.15))
    if has(df, "special"):
        parts.append((df[C["special"]].fillna(0).clip(0, 1), 0.10))
    if parts:
        wsum = sum(w for _, w in parts)
        add("quality_risk_score", sum(s.fillna(0.5) * w for s, w in parts) / wsum * 100)
    save_csv(df, paths.P["features"])
    if verbose:
        print("new features:", ", ".join(new))
        print("high cost batches (COPQ share of revenue at or above %.2f): %d" % (thr, int(df["high_copq_flag"].sum())))
    return df
