import datetime as dt
import hashlib
import json
import os

import numpy as np
import pandas as pd

from config import settings as S
from src.analytics import rules, scenarios
from src.utils import paths
from src.utils.columns import has
from src.utils.io_utils import _clean, load_model, read_json, save_json

C = S.COL
O = paths.OUTPUT
TAB = {"cost_mix": "understand", "cpk_by_flag": "understand", "correlation": "understand", "cost_components": "understand",
       "segment_sizes": "understand", "anomaly_rate_by_plant": "understand", "family_rate": "decide", "risk_score": "decide",
       "cpk_scatter": "decide", "feature_importance": "decide", "priority_breakdown": "decide",
       "plant_family_heat": "monitor", "monthly_trend": "monitor"}
RANK = {"P1_URGENT": 0, "P2_HIGH": 1, "P3_MEDIUM": 2, "P4_ROUTINE": 3}
WHEN = {"P1_URGENT": "Today", "P2_HIGH": "This week", "P3_MEDIUM": "This month", "P4_ROUTINE": "Next review"}


def _skip(reason):
    return {"status": "skipped", "reason": reason}


def _bigquery_available():
    if not S.BIGQUERY.get("project_id"):
        return False
    return bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")) or (paths.ROOT / S.BIGQUERY["credentials_file"]).exists()


def _load_from_bigquery():
    from google.cloud import bigquery
    b = S.BIGQUERY
    cred = paths.ROOT / b["credentials_file"]
    client = bigquery.Client.from_service_account_json(str(cred), project=b["project_id"]) if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") else bigquery.Client(project=b["project_id"])
    return client.query("SELECT * FROM `%s.%s.%s`" % (b["project_id"], b["dataset"], b["table"])).to_dataframe()


def _load_from_csv():
    return pd.read_csv(paths.P["features"])


def _load_data():
    if _bigquery_available():
        try:
            df = _load_from_bigquery()
            print("Source: BigQuery")
            return df, "bigquery"
        except Exception as exc:
            print("BigQuery failed, using CSV instead:", exc)
    print("Source: CSV")
    return _load_from_csv(), "csv"


def _ratio(d):
    r = d[C["revenue"]].sum()
    return 100.0 * d[C["copq"]].sum() / r if r > 0 else 0.0


def _hid(v):
    return "b_" + hashlib.sha1(str(v).encode()).hexdigest()[:8]


def _kpis(df):
    d = df[C["date"]]
    recent = df[d > d.max() - pd.Timedelta(days=30)]
    prior = df[(d <= d.max() - pd.Timedelta(days=30)) & (d > d.max() - pd.Timedelta(days=60))]
    items = []

    def add(key, label, fmt, fn, note=""):
        v = fn(df)
        tr = None
        if len(recent) >= 5 and len(prior) >= 5:
            a, b = fn(recent), fn(prior)
            tr = 100 * (a - b) / abs(b) if b else None
        items.append({"key": key, "label": label, "value": v, "format": fmt, "trend": tr, "note": note})

    add("batches", "Batches", "integer", lambda x: len(x))
    add("revenue", "Batch revenue", "currency", lambda x: x[C["revenue"]].sum())
    add("copq", "Total cost of poor quality", "currency", lambda x: x[C["copq"]].sum())
    add("copq_pct", "COPQ as % of revenue", "percent", _ratio, "Lower is better")
    add("margin", "Margin after quality", "percent", lambda x: 100 * x[C["gp"]].sum() / (x[C["revenue"]].sum() or 1))
    add("high_rate", "High cost batches", "percent", lambda x: 100 * x["high_copq_flag"].mean(), "Worst quarter by COPQ share")
    if has(df, "cpk"):
        add("cpk", "Average process Cpk", "decimal", lambda x: x[C["cpk"]].mean(), "1.33 is the usual target")
    if has(df, "escaped"):
        add("escaped", "Escaped defects", "integer", lambda x: x[C["escaped"]].sum())
    return {"items": items}


def _charts():
    items = []
    if paths.CHARTS_JSON.exists():
        for f in sorted(paths.CHARTS_JSON.glob("*.json")):
            c = read_json(f)
            if "id" in c:
                c["outcome"] = TAB.get(c["id"], "understand")
                items.append(c)
                save_json(c, f)
    return {"items": items} if len(items) >= 6 else _skip("fewer than six charts were produced")


def _segments(df, seg):
    if seg is None:
        return _skip("segments were not produced")
    m = df.merge(seg[[C["batch"], "segment"]], on=C["batch"])
    items = []
    for name in ("Low risk", "Medium risk", "High risk"):
        g = m[m["segment"] == name]
        if not len(g):
            continue
        s = {"Average process Cpk": g[C["cpk"]].mean() if has(g, "cpk") else None, "COPQ as % of revenue": _ratio(g),
             "High cost batches %": 100 * g["high_copq_flag"].mean()}
        items.append({"name": name, "size": len(g), "share": 100 * len(g) / len(m), "summary": s,
                      "description": "Batches grouped by similar defect, scrap, rework and capability measures, ranked by quality risk score."})
    return {"method": "KMeans with three clusters on standardised quality measures", "items": items}


def _anomalies(df, seg):
    if seg is None:
        return _skip("anomaly scoring was not produced")
    m = df.merge(seg, on=C["batch"])
    med = m.groupby(C["family"])[C["copq_pct"]].median()
    a = m[m["is_anomaly"] == 1].sort_values("anomaly_score", ascending=False).head(500)
    items = [{"id": _hid(r[C["batch"]]), "date": str(r[C["date"]])[:10], "metric": "COPQ as % of revenue", "value": r[C["copq_pct"]],
              "expected": med.get(r[C["family"]]), "score": r["anomaly_score"], "reason": r["anomaly_reason"]} for _, r in a.iterrows()]
    return {"method": "Isolation forest on standardised quality measures", "total": int(m["is_anomaly"].sum()),
            "rate": 100 * m["is_anomaly"].mean(), "items": items}


def _explorer(df):
    dims = [C[k] for k in ("plant", "family", "shift", "exp", "supplier") if has(df, k) and 2 <= df[C[k]].nunique() <= 20]
    if not dims:
        return _skip("no usable dimension for the explorer")
    y = df[C["copq_pct"]]
    tot = ((y - y.mean()) ** 2).sum() or 1
    score = {c: ((df.groupby(c)[C["copq_pct"]].mean() - y.mean()) ** 2 * df.groupby(c).size()).sum() / tot for c in dims}
    dims = sorted(dims, key=lambda c: -score[c])[:4]
    d = df.copy()
    for c in dims:
        d[c] = d[c].astype(str)
        small = d[c].value_counts()
        d[c] = d[c].where(~d[c].isin(small[small < 5].index), "Other")
    span = (d[C["date"]].max() - d[C["date"]].min()).days
    grain = "week" if span < 540 else "month"
    if grain == "month":
        d["_t"] = d[C["date"]].dt.to_period("M").astype(str)
    else:
        d["_t"] = d["week_start"].astype(str).str[:10]
    metrics = [{"key": "batches", "label": "Batches", "agg": "count", "format": "integer"},
               {"key": "revenue", "label": "Batch revenue", "agg": "sum", "format": "currency"},
               {"key": "copq", "label": "Total COPQ", "agg": "sum", "format": "currency"},
               {"key": "copq_pct", "label": "COPQ as % of revenue", "agg": "ratio", "format": "percent", "num": "copq", "den": "revenue"},
               {"key": "high_rate", "label": "High cost batch rate", "agg": "rate", "format": "percent"},
               {"key": "avg_cpk", "label": "Average Cpk", "agg": "mean", "format": "decimal"}]
    while dims:
        g = d.groupby(dims + ["_t"]).agg(n=(C["batch"], "count"), rev=(C["revenue"], "sum"), cp=(C["copq"], "sum"),
                                         hi=("high_copq_flag", "sum"), ck=(C["cpk"], "sum") if has(d, "cpk") else (C["batch"], "count"),
                                         ckn=(C["cpk"], "count") if has(d, "cpk") else (C["batch"], "count")).reset_index()
        rows = []
        for _, r in g.iterrows():
            rows.append({"d": {c: r[c] for c in dims}, "t": r["_t"], "m": {
                "batches": {"sum": r["n"], "n": r["n"]}, "revenue": {"sum": r["rev"], "n": r["n"]},
                "copq": {"sum": r["cp"], "n": r["n"]}, "high_rate": {"sum": r["hi"], "n": r["n"]},
                "avg_cpk": {"sum": r["ck"], "n": r["ckn"]}}})
        obj = {"dimensions": [{"key": c, "label": c.replace("_", " "), "values": sorted(d[c].unique().tolist())} for c in dims],
               "metrics": metrics, "time": {"grain": grain, "min": d["_t"].min(), "max": d["_t"].max()}, "rows": rows}
        if len(rows) <= 20000 and len(json.dumps(_clean(obj))) < 4_000_000:
            return obj
        dims = dims[:-1]
    return _skip("explorer would be too large")


def _recommendations(df, act):
    if act is None:
        return _skip("business actions were not produced")
    tot = df[C["copq"]].sum() or 1
    items = []
    for code, text in rules.ACTIONS.items():
        m = act[act["alerts"].str.contains(code, regex=False)]
        if not len(m):
            continue
        pr = min(m["priority"], key=lambda p: RANK[p])
        items.append({"priority": pr, "title": rules.LABELS[code], "action": text,
                      "evidence": "%d batches flagged; COPQ is %.2f%% of their revenue against %.2f%% overall." % (len(m), _ratio(df[df[C["batch"]].isin(m[C["batch"]])]), _ratio(df)),
                      "impact": "%s COPQ in flagged batches, %.1f%% of the total." % ("{:,.0f}".format(m[C["copq"]].sum()), 100 * m[C["copq"]].sum() / tot),
                      "when": WHEN[pr], "count": len(m)})
    items.sort(key=lambda r: (RANK[r["priority"]], -r["count"]))
    return {"items": items}


def _forecast():
    fc = pd.read_csv(paths.P["forecast"]) if paths.P["forecast"].exists() else None
    mt = read_json(paths.P["forecast_metrics"]) if paths.P["forecast_metrics"].exists() else {}
    if fc is None or mt.get("status") == "skipped":
        return _skip(mt.get("reason", "forecast was not produced"))
    h, f = fc[fc["kind"] == "history"], fc[fc["kind"] == "forecast"]
    return {"metric": mt["metric"], "unit": "percent", "horizon": mt["horizon"], "method": mt["method"],
            "history": [{"t": r["t"], "value": r["value"]} for _, r in h.iterrows()],
            "forecast": [{"t": r["t"], "value": r["value"], "low": r["low"], "high": r["high"]} for _, r in f.iterrows()],
            "error": {"mae": mt["mae"], "mape": mt["mape"], "baseline_mae": mt["baseline_mae"], "period": mt["period"]},
            "note": "Forecast of weekly COPQ as a percent of revenue. Error was measured on the last %d weeks held out." % mt["holdout_weeks"]}


def _typical(s, cat):
    return s.mode().iloc[0] if cat else float(s.median())


def _scorer(df):
    mt = read_json(paths.P["model_metrics"]) if paths.P["model_metrics"].exists() else {}
    if mt.get("status") == "skipped" or not mt:
        return _skip("no model was trained"), []
    if not mt.get("beats_baseline"):
        return _skip("the model was no better than the naive baseline"), []
    feats = read_json(paths.P["model_features"])
    model = load_model(paths.P["model"])
    pred = pd.read_csv(paths.P["predictions"])[[C["batch"], "split"]]
    d = df.merge(pred, on=C["batch"]).reset_index(drop=True)
    exposed = [r["feature"] for r in mt["importances"] if r["feature"] in feats["all"]][:8]
    if len(exposed) < 2:
        return _skip("fewer than two usable input fields"), []
    fields, typical = [], {}
    for f in exposed:
        s = d[f].dropna()
        if f in feats["categorical"]:
            typical[f] = s.mode().iloc[0]
            fields.append({"key": f, "label": f.replace("_", " "), "type": "category", "unit": "", "options": [str(o) for o in s.value_counts().index[:12]],
                           "default": str(typical[f]), "help": ""})
            continue
        typical[f] = float(s.median())
        if set(s.unique()) <= {0, 1}:
            fields.append({"key": f, "label": f.replace("_", " "), "type": "boolean", "unit": "", "min": 0, "max": 1, "step": 1,
                           "default": int(round(typical[f])), "options": ["No", "Yes"], "help": ""})
            continue
        lo, hi = float(s.quantile(0.01)), float(s.quantile(0.99))
        whole = bool((s % 1 == 0).all())
        step = 1 if whole else max(round((hi - lo) / 50, 3), 0.001)
        fields.append({"key": f, "label": f.replace("_", " "), "type": "number", "unit": "", "min": lo, "max": hi, "step": step,
                       "default": round(typical[f]) if whole else round(typical[f], 3), "help": ""})
    probs = model.predict_proba(d[feats["all"]])[:, 1] * 100
    q = np.percentile(probs, [33, 66])
    levels = [{"max": round(float(q[0]), 1), "label": "Low"}, {"max": round(float(q[1]), 1), "label": "Medium"}, {"max": 100, "label": "High"}]
    if not (levels[0]["max"] < levels[1]["max"] < 100):
        levels = [{"max": 33, "label": "Low"}, {"max": 66, "label": "Medium"}, {"max": 100, "label": "High"}]
    out = {"target": {"label": "Chance of a high cost batch", "format": "percent", "positive_label": "High cost batch"}, "task": "classification",
           "fields": fields, "risk_levels": levels, "note": "Fields not shown use typical values."}
    lr = model.named_steps["clf"]
    if lr.__class__.__name__ == "LogisticRegression":
        pre = model.named_steps["pre"]
        coef, b = lr.coef_[0], float(lr.intercept_[0])
        sc = pre.named_transformers_["num"].named_steps["sc"]
        terms = []
        for i, f in enumerate(feats["numeric"]):
            if f in exposed:
                terms.append({"field": f, "mean": float(sc.mean_[i]), "scale": float(sc.scale_[i]), "coef": float(coef[i])})
            else:
                b += (typical.get(f, float(d[f].median())) - sc.mean_[i]) / sc.scale_[i] * coef[i]
        ohe = pre.named_transformers_["cat"].named_steps["oh"]
        off = len(feats["numeric"])
        for j, f in enumerate(feats["categorical"]):
            cats = [str(c) for c in ohe.categories_[j]]
            cf = coef[off:off + len(cats)]
            off += len(cats)
            t = str(d[f].mode().iloc[0])
            ti = cats.index(t) if t in cats else 0
            b += float(cf[ti])
            if f in exposed:
                terms += [{"field": f, "value": c, "coef": float(v - cf[ti])} for c, v in zip(cats, cf) if c != cats[ti]]
        out.update({"type": "linear", "linear": {"intercept": b, "link": "logit", "terms": terms},
                    "fidelity": {"metric": "exact linear form", "value": 0, "n": int(len(d)), "quality": "good", "note": "Coefficients come straight from the fitted model."}})
    else:
        ref = d.groupby("high_copq_flag", group_keys=False).apply(lambda g: g.sample(frac=min(1.0, 1500 / len(d)), random_state=S.RANDOM_STATE))
        ref = ref.head(1500)
        y = model.predict_proba(ref[feats["all"]])[:, 1] * 100
        numf = [f for f in exposed if f not in feats["categorical"]]
        catf = [f for f in exposed if f in feats["categorical"]]
        std = {f: float(d[f].std()) or 1.0 for f in numf}
        k = min(25, len(ref))
        R = ref[numf].to_numpy(float) if numf else np.zeros((len(ref), 0))
        Rc = ref[catf].astype(str).to_numpy() if catf else np.zeros((len(ref), 0))
        sd = np.array([std[f] for f in numf]) if numf else np.ones(0)

        def est(xn, xc, skip=None):
            dist = np.sqrt((((R - xn) / sd) ** 2).sum(axis=1) + (Rc != xc).sum(axis=1))
            if skip is not None:
                dist[skip] = np.inf
            idx = np.argsort(dist)[:k]
            w = 1.0 / (dist[idx] + 0.05)
            return float((w * y[idx]).sum() / w.sum())

        test = d[d["split"] == "test"].head(300)
        pos = {ix: i for i, ix in enumerate(ref.index)}
        real = model.predict_proba(test[feats["all"]])[:, 1] * 100
        guess = [est(r[numf].to_numpy(float) if numf else np.zeros(0), r[catf].astype(str).to_numpy() if catf else np.zeros(0), pos.get(ix)) for ix, r in test.iterrows()]
        mae = float(np.abs(real - np.array(guess)).mean())
        rho = float(pd.Series(real).corr(pd.Series(guess), method="spearman"))
        out.update({"type": "knn", "knn": {"k": k, "std": std, "reference": [{"x": {f: (str(r[f]) if f in catf else float(r[f])) for f in exposed}, "y": float(v)} for (_, r), v in zip(ref.iterrows(), y)]},
                    "fidelity": {"metric": "mean absolute error on the 0 to 100 scale", "value": mae, "n": int(len(test)),
                                 "quality": "good" if mae < 5 else "fair" if mae < 10 else "low", "note": "Rank correlation with the real model %.2f." % rho}})
    return out, exposed


SHAPES = {"understand/kpis.json": ["items"], "understand/charts.json": ["items"], "understand/segments.json": ["items"],
          "understand/anomalies.json": ["items", "total", "rate"], "understand/explorer.json": ["dimensions", "metrics", "rows"],
          "decide/insights.json": ["items"], "decide/recommendations.json": ["items"], "decide/simulations/index.json": ["items"],
          "monitor/forecast.json": ["history", "forecast", "error"], "monitor/scorer.json": ["fields", "type"],
          "monitor/goal_progress.json": ["items"], "monitor/alerts.json": ["items"]}


def export():
    df, source = _load_data()
    df[C["date"]] = pd.to_datetime(df[C["date"]], errors="coerce")
    seg = pd.read_csv(paths.P["segments"]) if paths.P["segments"].exists() else None
    act = pd.read_csv(paths.P["actions"]) if paths.P["actions"].exists() else None
    state = read_json(paths.P["goal_state"]) if paths.P["goal_state"].exists() else {}
    ins = read_json(paths.P["insights"]) if paths.P["insights"].exists() else None
    scorer, exposed = _scorer(df)
    sims = [{"id": s, "title": t, "file": "decide/simulations/%s.json" % s} for s, t in scenarios.REGISTRY if (paths.SIMS / (s + ".json")).exists()]
    files = {
        "understand/kpis.json": _kpis(df), "understand/charts.json": _charts(), "understand/segments.json": _segments(df, seg),
        "understand/anomalies.json": _anomalies(df, seg), "understand/explorer.json": _explorer(df),
        "decide/insights.json": {"items": [dict(i, outcome="decide") for i in ins]} if ins else _skip("insights were not produced"),
        "decide/recommendations.json": _recommendations(df, act),
        "decide/goals.json": read_json(paths.P["goals_cfg"]) if paths.P["goals_cfg"].exists() else _skip("goals were not set"),
        "decide/simulations/index.json": {"items": sims} if sims else _skip("no scenarios were produced"),
        "monitor/forecast.json": _forecast(), "monitor/scorer.json": scorer,
        "monitor/goal_progress.json": {"items": state["progress"]} if state.get("progress") else _skip("goal progress was not produced"),
        "monitor/alerts.json": {"items": state.get("alerts", [])} if "alerts" in state else _skip("alerts were not produced"),
    }
    d = df[C["date"]]
    ok_date = d.notna().any()
    files["meta/summary.json"] = {"schema_version": "1", "project": S.PROJECT_TITLE, "domain": S.DOMAIN, "client_id": S.PROJECT_SLUG,
                                  "description": S.DESCRIPTION, "last_run": dt.datetime.now().isoformat(timespec="seconds"), "rows": len(df),
                                  "date_range": {"start": str(d.min().date()) if ok_date else None, "end": str(d.max().date()) if ok_date else None},
                                  "currency": S.CURRENCY if S.CURRENCY.get("code") else None, "locale": S.LOCALE, "source": source}
    files["meta/terminology.json"] = S.TERMINOLOGY
    mt = read_json(paths.P["model_metrics"]) if paths.P["model_metrics"].exists() else {}
    fe = read_json(paths.P["model_features"]) if paths.P["model_features"].exists() else {"all": []}
    files["meta/model_meta.json"] = {"model_name": mt.get("best"), "algorithm": mt.get("best"), "feature_count": len(fe["all"]),
                                     "feature_cols": fe["all"], "models_ready": bool(mt.get("beats_baseline"))}
    rec = read_json(paths.P["run_record"]) if paths.P["run_record"].exists() else {"started": "", "finished": "", "stages": []}
    prevlog = O / "meta" / "run_log.json"
    old = read_json(prevlog).get("runs", []) if prevlog.exists() else []
    files["meta/run_log.json"] = {"runs": ([rec] + [r for r in old if r.get("started") != rec.get("started")])[:20]}

    def ref(rel):
        return rel if rel in files and files[rel] is not None else None
    sch = scorer if scorer.get("fields") else None
    fcast = files["monitor/forecast.json"]
    contract = {
        "schema_version": "1", "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "project": {"name": S.PROJECT_TITLE, "domain": S.DOMAIN, "client_id": S.PROJECT_SLUG, "description": S.DESCRIPTION},
        "terminology": S.TERMINOLOGY,
        "source": {"type": "bigquery", **{k: S.BIGQUERY[k] for k in ("project_id", "dataset", "table", "credentials_file")}} if source == "bigquery" else {"type": "csv", "file": "data/processed/feature_store.csv"},
        "outcomes": {
            "understand": {k: "understand/%s.json" % k for k in ("kpis", "charts", "segments", "anomalies", "explorer")},
            "decide": {"insights": "decide/insights.json", "recommendations": "decide/recommendations.json", "simulations": "decide/simulations/index.json", "goals": "decide/goals.json"},
            "monitor": {"forecast": "monitor/forecast.json", "forecast_lookup": None, "scorer": "monitor/scorer.json", "goal_progress": "monitor/goal_progress.json", "alerts": "monitor/alerts.json"}},
        "model": {"type": "classification", "pkl_file": paths.P["model"].name, "feature_cols_file": paths.P["model_features"].name,
                  "input_fields": exposed, "output_label": "High cost batch", "horizon": "Before the batch ships"},
        "forecaster": {"input_schema": [{"name": f["key"], "type": "str" if f["type"] == "category" else "int" if f["type"] == "boolean" or f.get("step") == 1 else "float",
                                         "range": f.get("options") or [f.get("min"), f.get("max")]} for f in (sch["fields"] if sch else [])],
                       "output_schema": {"prediction": "int", "probability": "float", "risk_level": "str"}, "lookup_file": None},
        "frontend": {"framework": "react", "deploy_target": "cloudflare_workers"},
        "files": [{"filename": k, "purpose": "dashboard data"} for k in files]}
    if "status" in fcast and fcast["status"] == "skipped":
        pass
    for k in list(files):
        o = O / k
        body = files[k]
        bad = None
        if k in SHAPES and "status" not in body:
            miss = [x for x in SHAPES[k] if x not in body]
            bad = "missing keys: " + ", ".join(miss) if miss else None
        if bad:
            body = _skip(bad)
            files[k] = body
        save_json(body, o)
    for s in sims:
        pass
    contract["files"] = [{"filename": k, "purpose": "dashboard data"} for k in files] + [{"filename": s["file"], "purpose": "scenario table"} for s in sims]
    save_json(contract, paths.P["contract"])
    total = sum(p.stat().st_size for p in O.rglob("*.json")) / 1024
    print("%-40s %s" % ("File", "Status"))
    for k in files:
        print("%-40s %s" % (k, files[k].get("status", "ok") if isinstance(files[k], dict) else "ok"))
    print("Source:", source, "| contract:", paths.P["contract"].name, "| files:", len(contract["files"]) + 1, "| %.0f KB" % total)
    return contract
