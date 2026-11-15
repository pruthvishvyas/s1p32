import difflib
import re

import pandas as pd

from config import settings as S


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def resolve_columns(df):
    actual = list(df.columns)
    lookup = {_norm(c): c for c in actual}
    rename, missing, absent = {}, [], []
    for key, name in S.COL.items():
        if name in actual:
            continue
        hit = lookup.get(_norm(name))
        if hit is None:
            close = difflib.get_close_matches(_norm(name), list(lookup), n=1, cutoff=0.85)
            if close:
                hit = lookup[close[0]]
                print("column notice: using", hit, "for", name)
        if hit is not None:
            rename[hit] = name
        elif key in S.REQUIRED:
            missing.append(name)
        else:
            absent.append(name)
    if missing:
        guesses = {m: difflib.get_close_matches(m, actual, n=3, cutoff=0.4) for m in missing}
        raise ValueError("Required columns not found: " + ", ".join(missing) + ". Closest matches: "
                         + str(guesses) + ". Columns in the file: " + ", ".join(actual))
    return df.rename(columns=rename), absent


def has(df, *keys):
    return all(S.COL[k] in df.columns for k in keys)


def dates(df):
    return pd.to_datetime(df[S.COL["date"]], errors="coerce")
