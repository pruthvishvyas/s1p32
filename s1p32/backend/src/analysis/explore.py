import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from config import settings as S
from src.utils import paths
from src.utils.columns import has
from src.utils.io_utils import emit_chart, load_required, save_fig

C = S.COL
FLAG = "high_copq_flag"
plt.rcParams.update({"figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False})
NAMES = {0: "Standard cost", 1: "High cost"}


def _hist_rows(values, bins=15):
    counts, edges = np.histogram(values, bins=bins)
    return [{"label": "%.2f to %.2f" % (edges[i], edges[i + 1]), "value": int(counts[i])} for i in range(len(counts))]


def _overlay(df, col, name, title, question, fname):
    fig, ax = plt.subplots(figsize=(7, 4))
    s = df[col].dropna()
    bins = np.histogram_bin_edges(s, bins=20)
    for flag, color in ((0, "#4C78A8"), (1, "#E45756")):
        ax.hist(df.loc[df[FLAG] == flag, col].dropna(), bins=bins, alpha=0.6, color=color, label=NAMES[flag])
    ax.set_title(title)
    ax.set_xlabel(col)
    ax.legend()
    fig.tight_layout()
    save_fig(fig, fname)
    emit_chart(name, title, "histogram", question, col, "Batches", _hist_rows(s))


def cost_mix(df):
    counts = df[FLAG].map(NAMES).value_counts().reindex(["Standard cost", "High cost"]).fillna(0)
    fig, ax = plt.subplots(figsize=(5, 4))
    bars = ax.bar(counts.index, counts.values, color=["#4C78A8", "#E45756"])
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), int(b.get_height()), ha="center", va="bottom")
    ax.set_title("Batches by cost of poor quality")
    fig.tight_layout()
    save_fig(fig, "cost_mix.png")
    emit_chart("cost_mix", "Batches by cost of poor quality", "bar",
               "How many batches sit in the worst quarter by cost of poor quality?", "Group", "Batches",
               [{"label": k, "value": int(v)} for k, v in counts.items()])


def cpk_by_flag(df):
    _overlay(df, C["cpk"], "cpk_by_flag", "Process Cpk by cost group",
             "Do high cost batches run at lower process capability?", "cpk_by_flag.png")


def correlation(df):
    cols = [c for c in (C.get("cpk"), "batch_defect_rate_pct", "scrap_rate_pct", "rework_rate_pct",
                        "escape_rate_per_1000", "severity_index", C["copq_pct"], C["margin"], C.get("age"),
                        "quality_risk_score") if c in df.columns]
    corr = df[cols].corr().fillna(0)
    fig, ax = plt.subplots(figsize=(8, 6.5))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    im = ax.imshow(np.ma.array(corr.values, mask=mask), cmap="RdYlGn", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=60, ha="right", fontsize=7)
    ax.set_yticklabels(cols, fontsize=7)
    for i in range(len(cols)):
        for j in range(i + 1):
            ax.text(j, i, "%.2f" % corr.values[i, j], ha="center", va="center", fontsize=6)
    fig.colorbar(im)
    ax.set_title("Correlation of quality and cost measures")
    fig.tight_layout()
    save_fig(fig, "correlation.png")
    rows = [{"row": r, "col": c, "value": round(float(corr.loc[r, c]), 3)} for r in cols for c in cols]
    emit_chart("correlation", "Correlation of quality and cost measures", "heatmap",
               "Which quality measures move together with cost?", "Measure", "Measure", rows)


def family_rate(df):
    g = (df.groupby(C["family"])[FLAG].mean() * 100).sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(g.index, g.values, color="#E45756")
    ax.set_ylabel("High cost batches (%)")
    ax.set_title("High cost share by product family")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    save_fig(fig, "family_rate.png")
    emit_chart("family_rate", "High cost share by product family", "bar",
               "Which product families concentrate high cost batches?", "Product family", "High cost batches (%)",
               [{"label": k, "value": round(float(v), 2)} for k, v in g.items()])


def risk_score(df):
    _overlay(df, "quality_risk_score", "risk_score", "Quality risk score by cost group",
             "Does the risk score separate expensive batches?", "risk_score.png")


def cpk_scatter(df):
    s = df.sample(min(len(df), 1500), random_state=S.RANDOM_STATE)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for flag, color in ((0, "#4C78A8"), (1, "#E45756")):
        m = s[FLAG] == flag
        ax.scatter(s.loc[m, C["cpk"]], s.loc[m, C["copq_pct"]], s=10, alpha=0.6, color=color, label=NAMES[flag])
    ax.set_xlabel(C["cpk"])
    ax.set_ylabel(C["copq_pct"])
    ax.legend()
    ax.set_title("Process Cpk against cost of poor quality")
    fig.tight_layout()
    save_fig(fig, "cpk_scatter.png")
    emit_chart("cpk_scatter", "Process Cpk against cost of poor quality", "scatter",
               "How strongly does capability relate to cost?", C["cpk"], C["copq_pct"],
               [{"x": float(r[C["cpk"]]), "y": float(r[C["copq_pct"]]), "label": NAMES[int(r[FLAG])]}
                for _, r in s.dropna(subset=[C["cpk"], C["copq_pct"]]).iterrows()])


def plant_family_heat(df):
    pv = (df.pivot_table(index=C["plant"], columns=C["family"], values=FLAG, aggfunc="mean") * 100).fillna(0)
    fig, ax = plt.subplots(figsize=(8, 4))
    im = ax.imshow(pv.values, cmap="RdYlGn_r")
    ax.set_xticks(range(pv.shape[1]))
    ax.set_xticklabels(pv.columns, rotation=30, ha="right", fontsize=7)
    ax.set_yticks(range(pv.shape[0]))
    ax.set_yticklabels(pv.index, fontsize=7)
    for i in range(pv.shape[0]):
        for j in range(pv.shape[1]):
            ax.text(j, i, "%.0f" % pv.values[i, j], ha="center", va="center", fontsize=7)
    fig.colorbar(im)
    ax.set_title("High cost batches (%) by plant and family")
    fig.tight_layout()
    save_fig(fig, "plant_family_heat.png")
    rows = [{"row": str(r), "col": str(c), "value": round(float(pv.loc[r, c]), 2)} for r in pv.index for c in pv.columns]
    emit_chart("plant_family_heat", "High cost batches by plant and family", "heatmap",
               "Which plant and family pairs need attention?", "Product family", "Plant", rows)


def monthly_trend(df):
    d = pd.to_datetime(df[C["date"]], errors="coerce")
    g = df.assign(_m=d.dt.to_period("M")).dropna(subset=["_m"]).groupby("_m")[[C["copq"], C["revenue"]]].sum()
    g = g[g[C["revenue"]] > 0]
    pct = 100 * g[C["copq"]] / g[C["revenue"]]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot([str(i) for i in pct.index], pct.values, marker="o", color="#E45756")
    ax.set_ylabel("COPQ as % of revenue")
    ax.set_title("Monthly cost of poor quality")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    save_fig(fig, "monthly_trend.png")
    emit_chart("monthly_trend", "Monthly cost of poor quality", "line",
               "Is cost of poor quality rising or falling?", "Month", "COPQ as % of revenue",
               [{"label": str(i), "value": round(float(v), 3)} for i, v in pct.items()])


def cost_components(df):
    keys = [k for k in ("prev", "appr", "scrap_c", "rework_c", "warr", "recall") if has(df, k)]
    sums = pd.Series({C[k].replace("_Cost", "").replace("_", " "): df[C[k]].sum() for k in keys}).sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(sums.index, sums.values, color="#4C78A8")
    ax.set_title("Quality cost by component")
    fig.tight_layout()
    save_fig(fig, "cost_components.png")
    emit_chart("cost_components", "Quality cost by component", "bar",
               "Which cost buckets make up the quality bill?", "Component", "Cost",
               [{"label": k, "value": round(float(v), 2)} for k, v in sums.items()])


def run(verbose=True):
    df = load_required(paths.P["features"], "features")
    made = []
    for fn, need in ((cost_mix, [FLAG]), (cpk_by_flag, [C["cpk"]]), (correlation, []), (family_rate, [C["family"]]),
                     (risk_score, ["quality_risk_score"]), (cpk_scatter, [C["cpk"]]),
                     (plant_family_heat, [C["plant"], C["family"]]), (monthly_trend, [C["date"]]),
                     (cost_components, [])):
        if any(n not in df.columns for n in need):
            print("chart skipped (columns missing):", fn.__name__)
            continue
        try:
            fn(df)
            made.append(fn.__name__)
        except Exception as e:
            plt.close("all")
            print("chart skipped:", fn.__name__, type(e).__name__, e)
    if verbose:
        print("charts written:", ", ".join(made))
    if len(made) < 6:
        raise RuntimeError("fewer than six charts could be drawn")
    return made
