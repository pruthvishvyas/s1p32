import numpy as np
import pandas as pd

from config import settings as S
from src.utils import paths
from src.utils.columns import dates, has
from src.utils.io_utils import load_required, save_csv, save_json
from src.utils.runner import DataSizeSkip

C = S.COL


def _last(train, steps):
    return np.repeat(train[-1], steps)


def _mean4(train, steps):
    return np.repeat(train[-4:].mean(), steps)


def _trend(train, steps):
    t = np.arange(len(train))
    coef = np.polyfit(t, train, 1)
    return np.polyval(coef, np.arange(len(train), len(train) + steps))


METHODS = {"last value": _last, "mean of last four weeks": _mean4, "linear trend": _trend}


def run(verbose=True):
    df = load_required(paths.P["features"], "features")
    if not has(df, "date", "revenue", "copq"):
        raise DataSizeSkip("date or cost columns are missing")
    w = df.assign(_w=dates(df).dt.to_period("W").dt.start_time).dropna(subset=["_w"]).groupby("_w")[[C["copq"], C["revenue"]]].sum()
    w = w[w[C["revenue"]] > 0]
    y = (100 * w[C["copq"]] / w[C["revenue"]]).values
    n = len(y)
    if n < S.MIN_FORECAST_WEEKS:
        raise DataSizeSkip("only %d weeks of history, at least %d are needed" % (n, S.MIN_FORECAST_WEEKS))
    h = max(4, int(0.2 * n))
    train, test = y[:-h], y[-h:]
    scores = {}
    for name, fn in METHODS.items():
        p = fn(train, h)
        err = test - p
        nz = test != 0
        scores[name] = {"mae": float(np.abs(err).mean()), "mape": float((np.abs(err[nz]) / np.abs(test[nz])).mean() * 100) if nz.any() else None}
    best = min(scores, key=lambda k: scores[k]["mae"])
    base_mae = scores["last value"]["mae"]
    sd = float(np.std(test - METHODS[best](train, h)))
    fut = METHODS[best](y, S.FORECAST_PERIODS)
    last_t = w.index[-1]
    rows = [{"t": str(t.date()), "kind": "history", "value": float(v), "low": None, "high": None} for t, v in zip(w.index, y)]
    for i, v in enumerate(fut, 1):
        rows.append({"t": str((last_t + pd.Timedelta(days=7 * i)).date()), "kind": "forecast", "value": max(0.0, float(v)),
                     "low": max(0.0, float(v) - 1.28 * sd), "high": float(v) + 1.28 * sd})
    save_csv(pd.DataFrame(rows), paths.P["forecast"])
    save_json({"metric": "COPQ as a percent of revenue, weekly", "unit": "percent", "horizon": "%d weeks" % S.FORECAST_PERIODS,
               "method": best, "mae": scores[best]["mae"], "mape": scores[best]["mape"], "baseline_mae": base_mae,
               "period": "%s to %s" % (str(w.index[-h].date()), str(w.index[-1].date())), "holdout_weeks": h,
               "weeks_of_history": n, "all_methods": scores}, paths.P["forecast_metrics"])
    if verbose:
        print("held-out weeks:", h, "best method:", best, "MAE %.3f" % scores[best]["mae"], "baseline MAE %.3f" % base_mae)
    return rows
