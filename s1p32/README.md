# S1P32 quality analysis

## Business Problem

Quality cost is spread across scrap, rework, warranty and recall. This project shows where the cost of poor quality sits by plant, product family and process capability, and which batches need action first.

## The Core Finding

The worst quarter of batches by cost of poor quality holds 49.9% of total COPQ. Total COPQ is 3,472,487 on revenue of 144,948,333 (2.40% of revenue).

## Dataset

1,000 batches from 2025-10-01 to 2026-09-30, 63 columns after feature building.

## Project Structure

```
s1p32/
  .gitignore
  backend/
    export_for_frontend.py
    main.py
    requirements.txt
    config/
      __init__.py
      goals.json
      settings.py
    data/
    logs/
      last_run.json
    models/
      anomaly_model.joblib
      forecast_metrics.json
      leakage_log.json
      model_features.json
      model_hashes.json
      model_metrics.json
      primary_model.joblib
      segment_model.joblib
    notebooks/
      s1p32_analysis.ipynb
    output/
      frontend_contract.json
    reports/
      correlation.png
      cost_components.png
      cost_mix.png
      cpk_by_flag.png
      cpk_scatter.png
      family_rate.png
      feature_importance.png
      insights.json
      interactive_dashboard.html
      model_confusion_roc.png
      monthly_trend.png
      plant_family_heat.png
    src/
      __init__.py
  frontend/
    .dev.vars.example
    .gitignore
    README.md
    index.html
    package-lock.json
    package.json
    vite.config.js
    wrangler.toml
    public/
      _headers
      favicon.svg
      theme-init.js
    scripts/
      check-data.mjs
      refresh-data.mjs
    src/
      App.jsx
      main.jsx
```

## How It Works

Batch records are validated and cleaned, then turned into measures such as defect rate, scrap rate, escape rate and a quality risk score. Charts, a classifier for high cost batches, risk segments, anomaly screening and a weekly forecast follow. Plant rules assign a priority and action to each batch, and findings are written with their evidence.

## Models

| Model | Status |
| --- | --- |
| Batch cost classifier | Ready |
| Anomaly screen | Ready |
| Segment model | Ready |

## Key Insights

- The worst quarter of batches by COPQ share of revenue carries most of the quality bill. 256 of 1,000 batches hold 49.9% of total COPQ (1,733,355 of 3,472,487).
- Batches below the Cpk target cost more to correct. COPQ is 2.96% of revenue for 119 batches below Cpk 1.33 against 2.32% for 881 batches at or above it.
- Plants differ clearly in cost of poor quality. Plant B (Texas) runs at 2.51% of revenue (358 batches) against 2.28% at Plant C (Monterrey) (350 batches).

## How to Run

0. Frontend steps are in `frontend/README.md`.
1. Open the backend folder.
2. Run `pip install -r requirements.txt`.
3. Run `python main.py`, or run the notebook in `notebooks/` from top to bottom.
4. Run `python export_for_frontend.py` to write the dashboard data.
5. Open the workbook and charts in `reports/`.

## Output Files

| File | Purpose |
| --- | --- |
| reports/quality_report.xlsx | Workbook with summaries and the batch action list |
| reports/interactive_dashboard.html | Interactive overview page |
| reports/insights.json | Findings with evidence and actions |
| output/ | Dashboard data files |

## Tech Stack

Python, pandas, scikit-learn, matplotlib, plotly, openpyxl.
