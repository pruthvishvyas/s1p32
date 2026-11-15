import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, recall_score, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import settings as S
from src.utils import paths
from src.utils.columns import has
from src.utils.io_utils import emit_chart, load_required, save_csv, save_fig, save_json, save_model
from src.utils.runner import DataSizeSkip

C = S.COL
TARGET = "high_copq_flag"


def model_columns(df):
    num = [C[k] for k in S.MODEL_NUM_KEYS if has(df, k)]
    if "month_num" in df.columns:
        num.append("month_num")
    return num, [C[k] for k in S.MODEL_CAT_KEYS if has(df, k)]


def _pre(num, cat, scale):
    steps = [("imp", SimpleImputer(strategy="median"))] + ([("sc", StandardScaler())] if scale else [])
    return ColumnTransformer([
        ("num", Pipeline(steps), num),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore"))]), cat)], sparse_threshold=0)


def run(verbose=True):
    df = load_required(paths.P["features"], "features")
    num, cat = model_columns(df)
    if TARGET not in df.columns or not (num or cat):
        raise DataSizeSkip("target or process columns are missing")
    y = df[TARGET].astype(int)
    if y.nunique() < 2:
        raise DataSizeSkip("only one class present in the target")
    drops, keep = [], []
    for c in num:
        m = df[c].notna()
        try:
            auc = roc_auc_score(y[m], df.loc[m, c])
            auc = max(auc, 1 - auc)
        except ValueError:
            auc = 0.5
        corr = abs(np.corrcoef(df.loc[m, c], y[m])[0, 1]) if df.loc[m, c].nunique() > 1 else 0.0
        if auc > 0.97 or corr > 0.95:
            drops.append({"feature": c, "single_feature_auc": round(float(auc), 3), "abs_corr": round(float(corr), 3),
                          "reason": "too close to the target to be a fair predictor"})
        else:
            keep.append(c)
    num = keep
    feats = num + cat
    save_json({"dropped": drops}, paths.P["leakage_log"])
    tr, te = train_test_split(df.index, test_size=S.TEST_SIZE, stratify=y, random_state=S.RANDOM_STATE)
    Xtr, Xte, ytr, yte = df.loc[tr, feats], df.loc[te, feats], y[tr], y[te]
    if len(Xtr) < S.MIN_TRAIN_ROWS:
        raise DataSizeSkip("fewer than %d training rows" % S.MIN_TRAIN_ROWS)
    low_sample = bool(len(df) < 100 or y.value_counts().min() < 10)
    if low_sample:
        print("note: low sample, treat results with care")
    rs = S.RANDOM_STATE
    models = {
        "Logistic Regression": Pipeline([("pre", _pre(num, cat, True)), ("clf", LogisticRegression(max_iter=2000))]),
        "Random Forest": Pipeline([("pre", _pre(num, cat, False)), ("clf", RandomForestClassifier(n_estimators=300, min_samples_leaf=3, random_state=rs, n_jobs=1))]),
        "Gradient Boosting": Pipeline([("pre", _pre(num, cat, False)), ("clf", GradientBoostingClassifier(random_state=rs))]),
    }
    folds = int(min(5, ytr.value_counts().min()))
    results, fitted, probs = {}, {}, {}
    for name, mdl in models.items():
        cv_mean = cv_std = float("nan")
        if folds >= 2:
            sc = cross_val_score(mdl, Xtr, ytr, cv=StratifiedKFold(folds, shuffle=True, random_state=rs), scoring="roc_auc")
            cv_mean, cv_std = float(sc.mean()), float(sc.std())
        mdl.fit(Xtr, ytr)
        p = mdl.predict_proba(Xte)[:, 1]
        fitted[name], probs[name] = mdl, p
        results[name] = {"cv_auc_mean": cv_mean, "cv_auc_std": cv_std, "test_auc": float(roc_auc_score(yte, p)),
                         "test_acc": float(accuracy_score(yte, (p >= 0.5).astype(int)))}
        if verbose:
            r = results[name]
            print("%-20s CV-AUC %.3f +/- %.3f | Test-AUC %.3f | Test-Acc %.3f" % (name, cv_mean, cv_std, r["test_auc"], r["test_acc"]))
    best = max(results, key=lambda k: -1 if np.isnan(results[k]["cv_auc_mean"]) else results[k]["cv_auc_mean"])
    model, pb = fitted[best], probs[best]
    pred = (pb >= 0.5).astype(int)
    if verbose:
        print("best by cross-validation:", best)
        print(classification_report(yte, pred, zero_division=0))
    majority_acc = float(max(yte.mean(), 1 - yte.mean()))
    rule_acc = None
    if has(df, "cpk"):
        rule = (Xte[C["cpk"]] < S.THRESHOLDS["cpk_target"]).astype(int)
        rule_acc = float(accuracy_score(yte, rule))
    beats = bool(results[best]["test_auc"] >= 0.55)
    if verbose:
        print("baselines: majority accuracy %.3f, rule (Cpk below target) accuracy %s" % (majority_acc, "n/a" if rule_acc is None else "%.3f" % rule_acc))
        print("test AUC %.3f vs naive 0.500 -> %s" % (results[best]["test_auc"], "beats baseline" if beats else "no better than baseline"))
    imp = permutation_importance(model, Xte, yte, scoring="roc_auc", n_repeats=10, random_state=rs)
    imps = sorted([{"feature": f, "importance": float(v)} for f, v in zip(feats, imp.importances_mean)],
                  key=lambda r: -r["importance"])
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.5))
    cm = confusion_matrix(yte, pred, labels=[0, 1])
    axs[0].imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            axs[0].text(j, i, int(cm[i, j]), ha="center", va="center")
    axs[0].set_xticks([0, 1]); axs[0].set_yticks([0, 1])
    axs[0].set_xlabel("Predicted"); axs[0].set_ylabel("Actual"); axs[0].set_title("Confusion matrix (test)")
    fpr, tpr, _ = roc_curve(yte, pb)
    axs[1].plot(fpr, tpr, color="#E45756"); axs[1].plot([0, 1], [0, 1], "--", color="grey")
    axs[1].set_title("ROC (test, AUC %.3f)" % results[best]["test_auc"])
    fig.tight_layout()
    save_fig(fig, "model_confusion_roc.png")
    top = imps[:15][::-1]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh([r["feature"] for r in top], [r["importance"] for r in top], color="#4C78A8")
    ax.set_title("Top features by permutation importance (test AUC drop)")
    fig.tight_layout()
    save_fig(fig, "feature_importance.png")
    emit_chart("feature_importance", "Top predictors of a high cost batch", "bar",
               "Which process inputs matter most for batch cost?", "Process input", "Importance",
               [{"label": r["feature"], "value": round(r["importance"], 4)} for r in imps[:10]])
    save_model(model, paths.P["model"])
    save_json({"numeric": num, "categorical": cat, "all": feats}, paths.P["model_features"])
    out = pd.DataFrame({C["batch"]: df[C["batch"]], "split": "train"})
    out.loc[te, "split"] = "test"
    out["pred_high_copq"] = (model.predict_proba(df[feats])[:, 1] >= 0.5).astype(int)
    out["pred_prob"] = model.predict_proba(df[feats])[:, 1]
    save_csv(out, paths.P["predictions"])
    metrics = {"task": "classification", "target": TARGET, "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
               "positive_rate_pct": float(y.mean() * 100), "low_sample": low_sample, "models": results, "best": best,
               "baseline": {"majority_acc": majority_acc, "rule_acc": rule_acc, "auc": 0.5},
               "beats_baseline": beats, "recall_high": float(recall_score(yte, pred, zero_division=0)),
               "importances": imps, "leakage_dropped": drops, "cv_folds": folds}
    save_json(metrics, paths.P["model_metrics"])
    return metrics
