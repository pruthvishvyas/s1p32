from config import settings as S

ROOT = S.PROJECT_ROOT
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"
OUTPUT = ROOT / "output"
LOGS = ROOT / "logs"
CHARTS_JSON = OUTPUT / "understand" / "charts"
SIMS = OUTPUT / "decide" / "simulations"

P = {
    "raw": ROOT / "data" / "raw" / S.RAW_FILE,
    "validation": INTERIM / "validation_report.json",
    "cleaning_log": INTERIM / "cleaning_log.json",
    "target_info": INTERIM / "target_info.json",
    "clean": PROCESSED / "clean_data.csv",
    "features": PROCESSED / "feature_store.csv",
    "predictions": PROCESSED / "model_predictions.csv",
    "segments": PROCESSED / "segments_anomalies.csv",
    "forecast": PROCESSED / "forecast_output.csv",
    "actions": PROCESSED / "business_actions.csv",
    "goal_state": PROCESSED / "goal_state.json",
    "model": MODELS / "primary_model.joblib",
    "model_features": MODELS / "model_features.json",
    "model_metrics": MODELS / "model_metrics.json",
    "leakage_log": MODELS / "leakage_log.json",
    "segment_model": MODELS / "segment_model.joblib",
    "anomaly_model": MODELS / "anomaly_model.joblib",
    "forecast_metrics": MODELS / "forecast_metrics.json",
    "hashes": MODELS / "model_hashes.json",
    "insights": REPORTS / "insights.json",
    "workbook": REPORTS / "quality_report.xlsx",
    "dashboard_html": REPORTS / "interactive_dashboard.html",
    "goals_cfg": ROOT / "config" / "goals.json",
    "run_record": LOGS / "last_run.json",
    "contract": OUTPUT / "frontend_contract.json",
}
