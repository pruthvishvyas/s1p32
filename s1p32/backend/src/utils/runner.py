import datetime as dt
import time
import traceback
from pathlib import Path

from src.utils import paths
from src.utils.io_utils import MissingInput, read_json, save_json

RECORD = []
STARTED = dt.datetime.now().isoformat(timespec="seconds")


class DataSizeSkip(Exception):
    pass


def _ok(p):
    p = Path(p)
    return p.exists() and p.stat().st_size > 0


def _stand_in(p, status, reason):
    p = Path(p)
    if p.suffix == ".json" and not _ok(p):
        save_json({"status": status, "reason": reason}, p)


def run_stage(name, fn, requires=(), produces=()):
    t0 = time.time()
    status, reason = "ok", ""
    missing = [Path(p).name for p in requires if not _ok(p)]
    if missing:
        status, reason = "skipped", "missing upstream file: " + ", ".join(missing)
    else:
        try:
            fn()
        except (DataSizeSkip, MissingInput) as e:
            status, reason = "skipped", str(e)
        except Exception as e:
            traceback.print_exc()
            status, reason = "failed", type(e).__name__ + ": " + str(e)
        if status == "ok":
            bad = [Path(p).name for p in produces if not _ok(p)]
            if bad:
                status, reason = "failed", "expected output missing: " + ", ".join(bad)
    if status != "ok":
        for p in produces:
            _stand_in(p, status, reason)
        print("[%s] %s: %s" % (status.upper(), name, reason))
    else:
        print("[ok] %s (%.1fs)" % (name, time.time() - t0))
    RECORD.append({"name": name, "status": status, "seconds": round(time.time() - t0, 2), "reason": reason})
    return status


def verify_outputs(expected):
    rows = []
    for label, p in expected:
        p = Path(p)
        state = "ok"
        if not _ok(p):
            state = "missing"
        elif p.suffix == ".json":
            try:
                read_json(p)
            except Exception:
                state = "unreadable"
        rows.append((label, state, p.name))
    print("%-34s %-11s %s" % ("Stage", "Status", "Output"))
    for label, state, name in rows:
        print("%-34s %-11s %s" % (label, state, name))
    save_json({"started": STARTED, "finished": dt.datetime.now().isoformat(timespec="seconds"),
               "stages": RECORD}, paths.P["run_record"])
    return all(r[1] == "ok" for r in rows)
