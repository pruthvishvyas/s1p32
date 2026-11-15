import numpy as np
import pandas as pd

from config import settings as S
from src.utils import paths
from src.utils.columns import has
from src.utils.io_utils import load_required, save_json
from src.utils.runner import DataSizeSkip

C = S.COL
REGISTRY = [
    ("cpk_uplift", "Raise process capability"),
    ("special_cause_cut", "Cut special cause events"),
    ("scrap_rework_cut", "Reduce scrap and rework cost"),
]
OUTPUTS = [{"key": "copq_pct", "label": "COPQ as % of revenue", "format": "percent"},
           {"key": "saving", "label": "Quality cost saved", "format": "currency"},
           {"key": "margin_pct", "label": "Margin after quality %", "format": "percent"}]


def _table(xs, fn):
    return [{"x": round(float(x), 4), "values": {k: round(float(v), 4) for k, v in fn(x).items()}} for x in xs]


def _write(sid, title, desc, var, xs, fn, notes):
    save_json({"id": sid, "title": title, "description": desc, "variable": var, "outputs": OUTPUTS,
               "table": _table(xs, fn), "assumptions": notes}, paths.SIMS / (sid + ".json"))


def run(verbose=True):
    df = load_required(paths.P["features"], "features")
    if not has(df, "revenue", "copq", "copq_pct"):
        raise DataSizeSkip("cost columns are missing")
    rev, copq = float(df[C["revenue"]].sum()), float(df[C["copq"]].sum())
    base_pct = 100 * copq / (rev if rev > 0 else 1)
    base_margin = 100 * float(df[C["gp"]].sum()) / (rev if rev > 0 else 1) if has(df, "gp") else float("nan")

    def out(saving):
        saving = max(0.0, min(saving, copq))
        return {"copq_pct": 100 * (copq - saving) / (rev if rev > 0 else 1), "saving": saving, "margin_pct": base_margin + 100 * saving / (rev if rev > 0 else 1)}

    if has(df, "cpk"):
        m = df[[C["cpk"], C["copq_pct"]]].dropna()
        slope = float(np.polyfit(m[C["cpk"]], m[C["copq_pct"]], 1)[0]) if len(m) > 10 else 0.0
        slope = min(slope, 0.0)
        _write("cpk_uplift", "Raise process capability", "Projected effect of lifting Cpk on every batch by the chosen amount.",
               {"key": "cpk_uplift", "label": "Cpk increase", "unit": "Cpk points", "min": 0, "max": 0.6, "step": 0.02, "default": 0.2, "format": "decimal"},
               np.arange(0, 0.6001, 0.02), lambda x: out(-slope * x / 100 * rev),
               ["Uses the observed slope of COPQ share against Cpk across batches (%.2f points per Cpk point)." % slope,
                "An association in past batches, not a tested effect.", "Revenue and volumes held constant."])
    if has(df, "special"):
        sp = df[df[C["special"]] > 0]
        gap = max(0.0, float(sp[C["copq"]].mean() - df.loc[df[C["special"]] == 0, C["copq"]].mean())) if len(sp) and (df[C["special"]] == 0).any() else 0.0
        _write("special_cause_cut", "Cut special cause events", "Projected saving if a share of special cause batches ran like normal batches.",
               {"key": "reduction", "label": "Special cause batches avoided", "unit": "%", "min": 0, "max": 100, "step": 5, "default": 25, "format": "percent"},
               np.arange(0, 100.1, 5), lambda x: out(x / 100 * len(sp) * gap),
               ["Extra cost per special cause batch is the observed gap to normal batches (%.0f)." % gap, "Assumes the gap is removed in full for avoided events."])
    if has(df, "scrap_c", "rework_c"):
        pool = float(df[C["scrap_c"]].sum() + df[C["rework_c"]].sum())
        _write("scrap_rework_cut", "Reduce scrap and rework cost", "Direct saving from cutting scrap and rework cost by the chosen share.",
               {"key": "cut", "label": "Scrap and rework cost reduction", "unit": "%", "min": 0, "max": 50, "step": 2.5, "default": 10, "format": "percent"},
               np.arange(0, 50.1, 2.5), lambda x: out(x / 100 * pool),
               ["Straight arithmetic on booked scrap and rework cost.", "No change to shipped volume or price."])
    if verbose:
        print("scenario files written:", ", ".join(s for s, _ in REGISTRY if (paths.SIMS / (s + ".json")).exists()))
