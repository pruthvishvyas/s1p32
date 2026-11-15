import numpy as np
import pandas as pd

from config import settings as S
from src.utils import paths
from src.utils.columns import has
from src.utils.io_utils import load_required, read_csv_optional, read_json, save_json

C = S.COL
SEV = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _n(x):
    return "{:,.0f}".format(x)


def _ratio(d):
    r = d[C["revenue"]].sum()
    return 100.0 * d[C["copq"]].sum() / r if r > 0 else float("nan")


def _group_gap(df, key):
    g = {k: v for k, v in df.groupby(C[key]) if len(v) >= 20}
    if len(g) < 2:
        return None
    r = {k: _ratio(v) for k, v in g.items()}
    worst, best = max(r, key=r.get), min(r, key=r.get)
    return worst, best, r[worst], r[best], len(g[worst]), len(g[best])


def run(verbose=True):
    df = load_required(paths.P["features"], "features")
    seg = read_csv_optional(paths.P["segments"])
    act = read_csv_optional(paths.P["actions"])
    mt = read_json(paths.P["model_metrics"]) if paths.P["model_metrics"].exists() else {}
    out = []

    def add(category, finding, evidence, action, severity):
        out.append({"severity": severity, "category": category, "finding": finding, "evidence": evidence, "action": action})

    tot_copq, tot_rev = df[C["copq"]].sum(), df[C["revenue"]].sum()
    hi = df[df["high_copq_flag"] == 1]
    share = 100 * hi[C["copq"]].sum() / (tot_copq if tot_copq > 0 else 1)
    add("Cost Concentration", "The worst quarter of batches by COPQ share of revenue carries most of the quality bill.",
        "%s of %s batches hold %.1f%% of total COPQ (%s of %s)." % (_n(len(hi)), _n(len(df)), share, _n(hi[C["copq"]].sum()), _n(tot_copq)),
        "Review the high cost batch list with plant quality leads this week.", "HIGH")
    if has(df, "cpk"):
        lo, ok = df[df[C["cpk"]] < S.THRESHOLDS["cpk_target"]], df[df[C["cpk"]] >= S.THRESHOLDS["cpk_target"]]
        if len(lo) >= 20 and len(ok) >= 20:
            add("Process Capability", "Batches below the Cpk target cost more to correct.",
                "COPQ is %.2f%% of revenue for %s batches below Cpk %.2f against %.2f%% for %s batches at or above it." % (_ratio(lo), _n(len(lo)), S.THRESHOLDS["cpk_target"], _ratio(ok), _n(len(ok))),
                "Prioritise capability work on the lines producing the low Cpk batches.", "HIGH")
    g = _group_gap(df, "plant")
    if g:
        add("Plant Performance", "Plants differ clearly in cost of poor quality.",
            "%s runs at %.2f%% of revenue (%s batches) against %.2f%% at %s (%s batches)." % (g[0], g[2], _n(g[4]), g[3], g[1], _n(g[5])),
            "Share the practices of the best plant with the worst plant this month.", "HIGH")
    g = _group_gap(df, "family")
    if g:
        add("Product Performance", "One product family is the costliest to get right.",
            "%s carries COPQ of %.2f%% of revenue (%s batches) against %.2f%% for %s." % (g[0], g[2], _n(g[4]), g[3], g[1]),
            "Review the process plan and inspection points for the costliest family.", "MEDIUM")
    g = _group_gap(df, "supplier")
    if g:
        add("Supplier Quality", "Material suppliers show a gap in downstream cost.",
            "Batches on %s show COPQ of %.2f%% of revenue (%s batches) against %.2f%% on %s." % (g[0], g[2], _n(g[4]), g[3], g[1]),
            "Raise the gap in the next supplier review and request corrective actions.", "MEDIUM")
    if has(df, "special"):
        sp, ns = df[df[C["special"]] > 0], df[df[C["special"]] == 0]
        if len(sp) >= 20 and len(ns) >= 20:
            add("Process Stability", "Special cause events are followed by higher quality cost.",
                "%s special cause batches carry COPQ of %.2f%% of revenue against %.2f%% for %s others." % (_n(len(sp)), _ratio(sp), _ratio(ns), _n(len(ns))),
                "Hold a short cause review for every special cause event.", "MEDIUM")
    if has(df, "ext_fail"):
        ext = 100 * df[C["ext_fail"]].sum() / (tot_copq if tot_copq > 0 else 1)
        add("Failure Mix", "Failures reaching the customer are a measurable part of the quality bill.",
            "External failure cost is %.1f%% of total COPQ (%s of %s)." % (ext, _n(df[C["ext_fail"]].sum()), _n(tot_copq)),
            "Check final inspection coverage for the product families with most external failure cost.", "MEDIUM")
    if seg is not None:
        m = df.merge(seg[[C["batch"], "segment", "is_anomaly"]], on=C["batch"], how="inner")
        an = m[m["is_anomaly"] == 1]
        if len(an):
            add("Anomalies", "A small set of batches is statistically unusual.",
                "%s batches (%.1f%% of the dataset) are flagged; %.1f%% of them are high cost batches against %.1f%% elsewhere." % (
                    _n(len(an)), 100 * len(an) / len(m), 100 * an["high_copq_flag"].mean(), 100 * m.loc[m["is_anomaly"] == 0, "high_copq_flag"].mean()),
                "Walk through the flagged batches with the shift supervisors.", "MEDIUM")
        hs = m[m["segment"] == "High risk"]
        if len(hs):
            add("Risk Segments", "The high risk segment holds a disproportionate share of cost.",
                "%s high risk batches (%.1f%%) hold %.1f%% of COPQ." % (_n(len(hs)), 100 * len(hs) / len(m), 100 * hs[C["copq"]].sum() / (tot_copq if tot_copq > 0 else 1)),
                "Start improvement projects on the process patterns in this segment.", "LOW")
    if act is not None:
        p1 = int((act["priority"] == "P1_URGENT").sum())
        add("Alert Load", "Urgent alerts need immediate ownership.",
            "%s batches are P1 urgent and %s are P2 high out of %s." % (_n(p1), _n(int((act["priority"] == "P2_HIGH").sum())), _n(len(act))),
            "Assign an owner to every P1 batch today.", "MEDIUM")
    if mt.get("task") == "classification":
        top = mt["importances"][0]["feature"] if mt.get("importances") else "n/a"
        r = mt["models"][mt["best"]]
        if mt.get("beats_baseline"):
            add("Early Warning", "Process inputs known during production give an early warning of costly batches.",
                "Held-out test AUC %.2f (naive baseline 0.50) with %s as the leading input." % (r["test_auc"], top),
                "Use the score to select batches for extra inspection before shipping.", "MEDIUM")
        else:
            add("Early Warning", "Process inputs alone do not predict costly batches better than chance.",
                "Held-out test AUC %.2f against a naive 0.50, no better than baseline." % r["test_auc"],
                "Collect inspection and material data earlier before building a screening score.", "LOW")
    out.sort(key=lambda r: SEV[r["severity"]])
    for i, r in enumerate(out):
        if i < 3:
            r["severity"] = "HIGH"
    if verbose:
        for r in out:
            print("[%s] %s: %s | %s" % (r["severity"], r["category"], r["finding"], r["evidence"]))
    save_json(out, paths.P["insights"])
    return out
