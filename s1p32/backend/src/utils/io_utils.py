import datetime as dt
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.utils import paths


class MissingInput(Exception):
    pass


def _clean(o):
    if o is None or o is pd.NaT:
        return None
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, int):
        return o
    if isinstance(o, (float, np.floating, Decimal)):
        f = float(o)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return [_clean(v) for v in o.tolist()]
    if isinstance(o, (pd.Timestamp, dt.datetime, dt.date)):
        return o.isoformat()
    if isinstance(o, Path):
        return o.name
    return str(o)


def _target(path):
    p = Path(path).resolve()
    root = paths.ROOT.resolve()
    if p != root and root not in p.parents:
        raise ValueError("refusing to write outside the project: " + p.name)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _stamped(p):
    return p.with_name(p.stem + "_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + p.suffix)


def write_text(path, text):
    p = _target(path)
    text = text.replace(chr(0xfffd), "-")
    try:
        p.write_text(text, encoding="utf-8")
    except PermissionError:
        p = _stamped(p)
        p.write_text(text, encoding="utf-8")
        print("file was locked, saved as", p.name)
    return p


def save_json(obj, path):
    return write_text(path, json.dumps(_clean(obj), indent=2, ensure_ascii=False, allow_nan=False))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_csv(df, path):
    p = _target(path)
    try:
        df.to_csv(p, index=False, encoding="utf-8")
    except PermissionError:
        p = _stamped(p)
        df.to_csv(p, index=False, encoding="utf-8")
        print("file was locked, saved as", p.name)
    return p


def read_table(path):
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        df = None
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(path, encoding=enc)
                if df.shape[1] == 1:
                    df = pd.read_csv(path, encoding=enc, sep=None, engine="python")
                break
            except UnicodeDecodeError:
                continue
            except pd.errors.ParserError:
                df = pd.read_csv(path, encoding=enc, sep=None, engine="python")
                break
        if df is None:
            raise ValueError("could not read the data file with any common encoding: " + path.name)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.startswith("Unnamed:")]
    return df.dropna(how="all").dropna(axis=1, how="all")


def load_required(path, producer):
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        raise MissingInput(path.name + " is missing; run the " + producer + " stage first")
    return read_json(path) if path.suffix == ".json" else pd.read_csv(path)


def read_csv_optional(path):
    path = Path(path)
    return pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else None


def save_fig(fig, name):
    p = _target(paths.REPORTS / name)
    fig.savefig(p, dpi=150, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
    return p


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save_model(obj, path):
    p = _target(path)
    joblib.dump(obj, p)
    hp = paths.P["hashes"]
    hashes = read_json(hp) if hp.exists() else {}
    hashes[p.name] = _sha(p)
    save_json(hashes, hp)
    return p


def load_model(path):
    p = Path(path)
    if not p.exists():
        raise MissingInput(p.name + " is missing; run the model stage first")
    hp = paths.P["hashes"]
    hashes = read_json(hp) if hp.exists() else {}
    if hashes.get(p.name) and hashes[p.name] != _sha(p):
        raise ValueError("model file changed since it was saved: " + p.name)
    return joblib.load(p)


def emit_chart(cid, title, ctype, question, xl, yl, data):
    save_json({"id": cid, "title": title, "type": ctype, "question": question,
               "x_label": xl, "y_label": yl, "data": data}, paths.CHARTS_JSON / (cid + ".json"))
