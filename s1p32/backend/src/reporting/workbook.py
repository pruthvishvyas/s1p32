import datetime as dt

import numpy as np
import pandas as pd

from config import settings as S
from src.utils import paths
from src.utils.io_utils import load_required, read_csv_optional, read_json, write_text

C = S.COL
EXCEL_ROWS = 1000000


def _guard(df):
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: "'" + v if isinstance(v, str) and v and v[0] in "=+-@" else v)
    return df


def _sheet(name):
    return "".join(ch for ch in name if ch not in "[]:*?/\\")[:31]


def _by(df, key):
    g = df.groupby(C[key]).agg(batches=(C["batch"], "count"), revenue=(C["revenue"], "sum"), copq=(C["copq"], "sum"),
                               avg_cpk=(C["cpk"], "mean") if C["cpk"] in df else (C["batch"], "count"),
                               high_cost_rate_pct=("high_copq_flag", lambda s: 100 * s.mean()))
    g["copq_pct_of_revenue"] = 100 * g["copq"] / g["revenue"].replace(0, 1)
    return g.reset_index().sort_values("copq_pct_of_revenue", ascending=False)


def run(verbose=True):
    df = load_required(paths.P["features"], "features")
    seg = read_csv_optional(paths.P["segments"])
    act = read_csv_optional(paths.P["actions"])
    rev, copq = df[C["revenue"]].sum(), df[C["copq"]].sum()
    summary = pd.DataFrame({"Measure": ["Batches", "Revenue", "Total COPQ", "COPQ as % of revenue", "Margin after quality %",
                                        "High cost batches", "Average Process Cpk"],
                            "Value": [len(df), rev, copq, 100 * copq / (rev if rev > 0 else 1),
                                      100 * df[C["gp"]].sum() / (rev if rev > 0 else 1), int(df["high_copq_flag"].sum()),
                                      df[C["cpk"]].mean() if C["cpk"] in df else np.nan]})
    none = pd.DataFrame({"Note": ["Not available: the upstream stage did not run"]})
    prio = (act.groupby("priority").agg(batches=(C["batch"], "count"), copq=(C["copq"], "sum")).reset_index() if act is not None else none)
    if seg is not None:
        m = df.merge(seg[[C["batch"], "segment"]], on=C["batch"], how="left")
        segs = m.groupby("segment").agg(batches=(C["batch"], "count"), copq=(C["copq"], "sum"),
                                       avg_risk_score=("quality_risk_score", "mean")).reset_index()
    else:
        segs = none
    plant_family = pd.concat([_by(df, "plant"), _by(df, "family")], ignore_index=True).fillna("")
    cap = df.head(EXCEL_ROWS - 2)
    sheets = {"Quality Summary": summary, "Priority Analysis": prio, "Segment Summary": segs,
              "Plant and Family Costs": plant_family, "All Records": cap}
    target = paths.P["workbook"]
    for attempt in (target, target.with_name("quality_report_" + dt.datetime.now().strftime("%H%M%S") + ".xlsx")):
        try:
            with pd.ExcelWriter(attempt, engine="openpyxl") as xw:
                for name, frame in sheets.items():
                    _guard(frame).to_excel(xw, sheet_name=_sheet(name), index=False)
                p = xw.book.properties
                p.creator, p.lastModifiedBy, p.title = "", "", S.PROJECT_TITLE
            break
        except PermissionError:
            print("workbook is open elsewhere, saving under a new name")
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        fig = make_subplots(rows=2, cols=2, subplot_titles=("High cost batches by family (%)", "Risk score", "Cpk against COPQ share", "Batches by priority"))
        r = df.groupby(C["family"])["high_copq_flag"].mean() * 100
        fig.add_trace(go.Bar(x=list(r.index), y=r.values), row=1, col=1)
        fig.add_trace(go.Histogram(x=df["quality_risk_score"]), row=1, col=2)
        if C["cpk"] in df:
            fig.add_trace(go.Scatter(x=df[C["cpk"]], y=df[C["copq_pct"]], mode="markers", marker={"size": 4}), row=2, col=1)
        if act is not None:
            pc = act["priority"].value_counts()
            fig.add_trace(go.Bar(x=list(pc.index), y=pc.values), row=2, col=2)
        fig.update_layout(title_text="Quality overview", showlegend=False)
        write_text(paths.P["dashboard_html"], fig.to_html(include_plotlyjs=True, full_html=True))
    except ImportError:
        write_text(paths.P["dashboard_html"], "<html><head><title>Quality overview</title></head><body>Install plotly to build this page.</body></html>")
    ins = read_json(paths.P["insights"]) if paths.P["insights"].exists() else []
    print("=" * 60)
    print("Batches: %s | COPQ share of revenue: %.2f%% | High cost batches: %s" % (
        "{:,}".format(len(df)), 100 * copq / (rev if rev > 0 else 1), "{:,}".format(int(df["high_copq_flag"].sum()))))
    if seg is not None:
        print("Anomalies:", int(seg["is_anomaly"].sum()))
    if act is not None:
        print("P1 batches:", int((act["priority"] == "P1_URGENT").sum()))
    print("Insights:", len(ins))
    print("=" * 60)
