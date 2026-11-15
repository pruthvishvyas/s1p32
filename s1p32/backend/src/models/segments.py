import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from config import settings as S
from src.utils import paths
from src.utils.io_utils import emit_chart, load_required, save_csv, save_fig, save_model
from src.utils.runner import DataSizeSkip

C = S.COL
LABELS = {"batch_defect_rate_pct": "batch defect rate", "scrap_rate_pct": "scrap rate", "rework_rate_pct": "rework rate",
          "escape_rate_per_1000": "escaped defects per 1000 shipped", "Process_Cpk": "process Cpk",
          "COPQ_pct_of_Revenue": "COPQ share of revenue"}


def run(verbose=True):
    df = load_required(paths.P["features"], "features")
    cols = [c for c in (C["cpk"], C["copq_pct"], "batch_defect_rate_pct", "scrap_rate_pct", "rework_rate_pct",
                        "escape_rate_per_1000") if c in df.columns]
    if len(cols) < 3 or "quality_risk_score" not in df.columns:
        raise DataSizeSkip("fewer than three numeric measures available for segments")
    if len(df) < 30:
        raise DataSizeSkip("too few batches for segments")
    X = df[cols].fillna(df[cols].median())
    Z = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=3, n_init=10, random_state=S.RANDOM_STATE).fit(Z)
    order = df.groupby(km.labels_)["quality_risk_score"].mean().sort_values().index.tolist()
    names = {c: n for c, n in zip(order, ["Low risk", "Medium risk", "High risk"])}
    seg = pd.Series(km.labels_).map(names)
    iso = IsolationForest(n_estimators=200, contamination=S.ANOMALY_CONTAMINATION, random_state=S.RANDOM_STATE).fit(Z)
    is_anom = (iso.predict(Z) == -1).astype(int)
    score = -iso.decision_function(Z)
    big = np.abs(Z).argmax(axis=1)
    reason = [("%s unusually %s" % (LABELS.get(cols[j], cols[j]), "high" if Z[i, j] > 0 else "low")) for i, j in enumerate(big)]
    pc = PCA(n_components=2, random_state=S.RANDOM_STATE).fit_transform(Z)
    out = pd.DataFrame({C["batch"]: df[C["batch"]], "segment": seg, "is_anomaly": is_anom, "anomaly_score": score,
                        "anomaly_reason": reason, "pc1": pc[:, 0], "pc2": pc[:, 1]})
    save_csv(out, paths.P["segments"])
    save_model({"scaler_cols": cols, "kmeans": km}, paths.P["segment_model"])
    save_model(iso, paths.P["anomaly_model"])
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.5))
    for n, color in (("Low risk", "#59A14F"), ("Medium risk", "#F28E2B"), ("High risk", "#E15759")):
        m = seg == n
        axs[0].scatter(pc[m, 0], pc[m, 1], s=8, alpha=0.6, color=color, label=n)
    axs[0].legend(); axs[0].set_title("Batch segments")
    axs[1].scatter(pc[is_anom == 0, 0], pc[is_anom == 0, 1], s=8, alpha=0.4, color="#4C78A8", label="Normal")
    axs[1].scatter(pc[is_anom == 1, 0], pc[is_anom == 1, 1], s=14, color="#E15759", label="Anomaly")
    axs[1].legend(); axs[1].set_title("Anomalous batches")
    fig.tight_layout()
    save_fig(fig, "segments_anomalies.png")
    sizes = seg.value_counts().reindex(["Low risk", "Medium risk", "High risk"]).fillna(0)
    emit_chart("segment_sizes", "Batches by risk segment", "bar", "How many batches sit in each risk segment?",
               "Segment", "Batches", [{"label": k, "value": int(v)} for k, v in sizes.items()])
    rate = df.assign(a=is_anom).groupby(C["plant"])["a"].mean() * 100
    emit_chart("anomaly_rate_by_plant", "Anomaly rate by plant", "bar", "Which plants produce the most unusual batches?",
               "Plant", "Anomalous batches (%)", [{"label": k, "value": round(float(v), 2)} for k, v in rate.items()])
    if verbose:
        print("segment sizes:", sizes.astype(int).to_dict())
        print("anomalies:", int(is_anom.sum()), "high cost rate among anomalies %.1f%% vs %.1f%% otherwise" % (
            df.loc[is_anom == 1, "high_copq_flag"].mean() * 100, df.loc[is_anom == 0, "high_copq_flag"].mean() * 100))
    return out
