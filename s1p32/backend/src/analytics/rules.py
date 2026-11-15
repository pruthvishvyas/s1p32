import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from config import settings as S
from src.utils import paths
from src.utils.io_utils import emit_chart, load_required, read_json, save_csv, save_fig

C = S.COL
T = S.THRESHOLDS
LABELS = {
    "CPK_BELOW_1.0": "Process Cpk below 1.0",
    "CPK_BELOW_TARGET": "Process Cpk below target",
    "SPECIAL_CAUSE": "Special cause event",
    "ESCAPED_DEFECTS": "Defects escaped to customers",
    "RECALL_COST": "Recall cost booked",
    "NEGATIVE_MARGIN": "Negative margin after quality",
    "HIGH_COPQ": "High cost of poor quality",
    "LATE_BATCH": "Late batch",
}
ACTIONS = {
    "CPK_BELOW_1.0": "Stop and re-centre the process before the next batch",
    "CPK_BELOW_TARGET": "Review process capability and tooling this week",
    "SPECIAL_CAUSE": "Investigate the special cause before release",
    "ESCAPED_DEFECTS": "Add containment inspection at shipping",
    "RECALL_COST": "Open a recall review with the plant quality lead",
    "NEGATIVE_MARGIN": "Reprice or pause this product family at this plant",
    "HIGH_COPQ": "Review scrap, rework and warranty drivers for the batch",
    "LATE_BATCH": "Check scheduling and rework queue for the plant",
}
P1 = {"RECALL_COST", "NEGATIVE_MARGIN", "CPK_BELOW_1.0"}
P2 = {"ESCAPED_DEFECTS", "SPECIAL_CAUSE"}


def _num(row, key):
    v = row.get(C[key]) if key in C else None
    return v if v is not None and pd.notna(v) else None


def assign_alert(row, high_thr):
    a = []
    cpk = _num(row, "cpk")
    if cpk is not None and cpk < T["cpk_critical"]:
        a.append("CPK_BELOW_1.0")
    elif cpk is not None and cpk < T["cpk_target"]:
        a.append("CPK_BELOW_TARGET")
    if (_num(row, "special") or 0) > 0:
        a.append("SPECIAL_CAUSE")
    if (_num(row, "escaped") or 0) > 0:
        a.append("ESCAPED_DEFECTS")
    if (_num(row, "recall") or 0) > 0:
        a.append("RECALL_COST")
    m = _num(row, "margin")
    if m is not None and m < 0:
        a.append("NEGATIVE_MARGIN")
    cp = _num(row, "copq_pct")
    if cp is not None and cp >= high_thr:
        a.append("HIGH_COPQ")
    if (_num(row, "delay") or 0) > T["delay_days"]:
        a.append("LATE_BATCH")
    return "|".join(a) if a else "NORMAL"


def priority_level(alerts):
    codes = set(alerts.split("|"))
    if codes & P1:
        return "P1_URGENT"
    if codes & P2:
        return "P2_HIGH"
    if codes - {"NORMAL"}:
        return "P3_MEDIUM"
    return "P4_ROUTINE"


def recommend(alerts):
    acts = [ACTIONS[c] for c in alerts.split("|") if c in ACTIONS]
    return "; ".join(acts) if acts else "No action needed"


def run(verbose=True):
    df = load_required(paths.P["features"], "features")
    thr = read_json(paths.P["target_info"])["threshold"]
    df["alerts"] = df.apply(lambda r: assign_alert(r, thr), axis=1)
    df["priority"] = df["alerts"].map(priority_level)
    df["recommendations"] = df["alerts"].map(recommend)
    keep = [c for c in (C["batch"], C["date"], C["plant"], C["family"], C["cpk"], C["copq"], C["copq_pct"],
                        "high_copq_flag", "quality_risk_score") if c in df.columns]
    save_csv(df[keep + ["alerts", "priority", "recommendations"]], paths.P["actions"])
    counts = df["priority"].value_counts().reindex(["P1_URGENT", "P2_HIGH", "P3_MEDIUM", "P4_ROUTINE"]).fillna(0)
    if verbose:
        print(counts.astype(int).to_string())
        print((df.groupby("priority")["high_copq_flag"].mean() * 100).round(1).to_string())
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(counts.index, counts.values, color=["#E15759", "#F28E2B", "#EDC948", "#59A14F"])
    ax.set_title("Batches by priority")
    plt.setp(ax.get_xticklabels(), rotation=15)
    fig.tight_layout()
    save_fig(fig, "priority_breakdown.png")
    emit_chart("priority_breakdown", "Batches by priority", "bar", "How many batches need action now?",
               "Priority", "Batches", [{"label": k, "value": int(v)} for k, v in counts.items()])
    return df
