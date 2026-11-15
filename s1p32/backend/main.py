import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.analysis import explore
from src.analytics import insights, rules, scenarios, targets
from src.data import cleaning, loading
from src.features import build
from src.models import classifier, forecasting, segments
from src.reporting import workbook
from src.utils import paths
from src.utils.runner import run_stage, verify_outputs

P = paths.P
STAGES = [
    ("Data validation", loading.validate, (P["raw"],), (P["validation"],)),
    ("Data cleaning", cleaning.clean, (P["raw"],), (P["clean"], P["cleaning_log"])),
    ("Feature table", build.build, (P["clean"],), (P["features"], P["target_info"])),
    ("Exploratory charts", explore.run, (P["features"],), ()),
    ("Batch cost classifier", classifier.run, (P["features"],), (P["model_metrics"],)),
    ("Batch segments and anomalies", segments.run, (P["features"],), (P["segments"],)),
    ("Weekly COPQ forecast", forecasting.run, (P["features"],), (P["forecast_metrics"],)),
    ("Alerts and actions", rules.run, (P["features"],), (P["actions"],)),
    ("What-if scenarios", scenarios.run, (P["features"],), ()),
    ("Goals and alerts", targets.run, (P["features"],), (P["goal_state"],)),
    ("Insights", insights.run, (P["features"],), (P["insights"],)),
    ("Workbook and overview page", workbook.run, (P["features"],), (P["workbook"], P["dashboard_html"])),
]


def run_one(label):
    for name, fn, req, prod in STAGES:
        if name == label:
            return run_stage(name, fn, req, prod)
    raise KeyError(label)


def finish():
    expected = [(n, p) for n, _, _, prod in STAGES for p in prod]
    return verify_outputs(expected)


def run_all():
    for name, _, _, _ in STAGES:
        run_one(name)
    return finish()


if __name__ == "__main__":
    run_all()
