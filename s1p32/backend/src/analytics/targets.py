import numpy as np
import pandas as pd

from config import settings as S
from src.utils import paths
from src.utils.columns import dates, has
from src.utils.io_utils import load_required, read_json, save_json
from src.utils.runner import DataSizeSkip

C = S.COL
DEFAULT_GOALS = {
    "revenue_target": {"value": None, "unit": "monthly", "client_sets": True},
    "copq_ceiling_pct": {"value": None, "unit": "percent", "client_sets": True,
                         "description": "Highest acceptable cost of poor quality as a percent of revenue"},
    "alert_drop_pct": {"value": 20, "unit": "percent", "description": "Alert if monthly revenue drops by this share"},
    "forecast_horizon": {"value": 30, "unit": "days"},
}


def load_goals():
    p = paths.P["goals_cfg"]
    if p.exists():
        return read_json(p)
    save_json(DEFAULT_GOALS, p)
    return DEFAULT_GOALS


def run(verbose=True):
    goals = load_goals()
    df = load_required(paths.P["features"], "features")
    if not has(df, "date", "revenue", "copq"):
        raise DataSizeSkip("date or cost columns are missing")
    d = dates(df)
    m = df.assign(_m=d.dt.to_period("M")).dropna(subset=["_m"]).groupby("_m").agg(
        rev=(C["revenue"], "sum"), copq=(C["copq"], "sum"), n=(C["batch"], "count"))
    if len(m) < 1:
        raise DataSizeSkip("no dated rows")
    last = m.iloc[-1]
    prev = m.iloc[-2] if len(m) > 1 else None
    month = str(m.index[-1])
    last_pct = 100 * last["copq"] / (last["rev"] if last["rev"] > 0 else 1)
    prog, alerts = [], []
    tgt = goals.get("revenue_target", {}).get("value")
    pct = 100 * last["rev"] / tgt if tgt else None
    prog.append({"key": "revenue_target", "label": "Monthly revenue", "target": tgt, "actual": float(last["rev"]), "unit": "currency",
                 "pct": pct, "status": "no_target" if pct is None else ("on_track" if pct >= 100 else "at_risk" if pct >= 80 else "off_track")})
    ceil = goals.get("copq_ceiling_pct", {}).get("value")
    st = "no_target" if ceil is None else ("on_track" if last_pct <= ceil else "at_risk" if last_pct <= 1.1 * ceil else "off_track")
    prog.append({"key": "copq_ceiling_pct", "label": "COPQ as % of revenue", "target": ceil, "actual": last_pct, "unit": "percent",
                 "pct": (100 * ceil / (last_pct if last_pct > 0 else 1)) if ceil else None, "status": st})
    drop_lim = goals.get("alert_drop_pct", {}).get("value")
    if prev is not None and drop_lim and last["n"] >= 0.8 * prev["n"]:   # skip partial months
        drop = 100 * (prev["rev"] - last["rev"]) / (prev["rev"] if prev["rev"] > 0 else 1)
        prog.append({"key": "alert_drop_pct", "label": "Revenue drop versus prior month", "target": drop_lim, "actual": max(0.0, drop),
                     "unit": "percent", "pct": max(0.0, drop) / drop_lim * 100, "status": "off_track" if drop > drop_lim else "on_track"})
        if drop > drop_lim:
            alerts.append({"severity": "HIGH", "title": "Revenue drop", "message": "Revenue fell %.1f%% against the previous month." % drop,
                           "metric": "monthly revenue change", "value": -drop, "threshold": -drop_lim, "since": month})
    if len(m) > 3:
        recent = m.iloc[-4:-1]
        base = 100 * recent["copq"].sum() / (recent["rev"].sum() if recent["rev"].sum() > 0 else 1)
        if last_pct > S.ALERT_RATIO * base:
            alerts.append({"severity": "MEDIUM", "title": "Cost of poor quality rising",
                           "message": "COPQ is %.1f%% of revenue against %.1f%% over the three months before." % (last_pct, base),
                           "metric": "COPQ share of revenue", "value": last_pct, "threshold": S.ALERT_RATIO * base, "since": month})
    if ceil is not None and last_pct > ceil:
        alerts.append({"severity": "HIGH", "title": "COPQ above ceiling", "message": "COPQ share of revenue is above the agreed ceiling.",
                       "metric": "COPQ share of revenue", "value": last_pct, "threshold": ceil, "since": month})
    if has(df, "cpk"):
        recent_rows = df[d > d.max() - pd.Timedelta(days=30)]
        low = int((recent_rows[C["cpk"]] < S.THRESHOLDS["cpk_critical"]).sum())
        if low:
            alerts.append({"severity": "HIGH", "title": "Batches below Cpk 1.0", "message": "%d batches in the last 30 days ran below Cpk 1.0." % low,
                           "metric": "batches below Cpk 1.0", "value": low, "threshold": 0, "since": str(d.max().date())})
    save_json({"progress": prog, "alerts": alerts}, paths.P["goal_state"])
    if verbose:
        print("goal items:", len(prog), "alerts:", len(alerts))
