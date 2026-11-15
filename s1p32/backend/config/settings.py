from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_SLUG = "s1p32"
PROJECT_TITLE = "S1P32 quality analysis"
RAW_FILE = "s1p32.csv"
DOMAIN = "Manufacturing quality"
DESCRIPTION = "Cost of poor quality, defects and margin by production batch"

RANDOM_STATE = 42
TEST_SIZE = 0.25
ANOMALY_CONTAMINATION = 0.05   # about one batch in twenty is a fair load for an engineer to review
HIGH_COPQ_QUANTILE = 0.75      # worst quarter of batches by cost of poor quality as a share of revenue
IQR_CAP_FACTOR = 3.0           # wide fence, only extreme process readings are clipped
MIN_TRAIN_ROWS = 20
FORECAST_PERIODS = 4           # four weeks matches the monthly planning cycle
MIN_FORECAST_WEEKS = 16        # fewer weeks cannot hold back a useful test window
ALERT_RATIO = 1.2              # a month 20 percent above its recent average is worth a look

COL = {
    "batch": "Batch_ID", "date": "Production_Date", "month": "Month", "plant": "Plant",
    "family": "Product_Family", "shift": "Shift", "exp": "Operator_Experience",
    "age": "Machine_Age_Years", "supplier": "Material_Supplier", "ramp": "New_Product_Ramp_Flag",
    "size": "Batch_Size", "cpk": "Process_Cpk", "special": "Special_Cause_Event",
    "sample_n": "Sample_Size_Inspected", "sample_def": "Defects_Found_in_Sample",
    "sample_rate": "Sample_Defect_Rate_pct", "defects": "Actual_Defects_in_Batch",
    "crit": "Critical_Defects", "major": "Major_Defects", "minor": "Minor_Defects",
    "dtype": "Dominant_Defect_Type", "inspection": "Inspection_Result", "scrap_u": "Scrap_Units",
    "rework_u": "Rework_Units", "shipped": "Units_Shipped", "escaped": "Escaped_Defects",
    "field_def": "Field_Defects_Reported", "complaints": "Customer_Complaints",
    "delay": "Delay_Days", "unit_cost": "Standard_Unit_Cost", "price": "Selling_Price",
    "revenue": "Batch_Revenue", "cogs": "Batch_COGS", "prev": "Prevention_Cost",
    "appr": "Appraisal_Cost", "scrap_c": "Scrap_Cost", "rework_c": "Rework_Cost",
    "warr": "Warranty_Cost", "recall": "Recall_Cost", "int_fail": "Internal_Failure_Cost",
    "ext_fail": "External_Failure_Cost", "copq": "Total_COPQ", "copq_pct": "COPQ_pct_of_Revenue",
    "gp": "Gross_Profit_After_Quality", "margin": "Margin_pct",
}
REQUIRED = {"batch", "date", "plant", "family", "revenue", "copq", "copq_pct", "margin", "gp"}
TEXT_KEYS = ["batch", "month", "plant", "family", "shift", "exp", "supplier", "dtype", "inspection"]
CAT_CASE_KEYS = ["month", "plant", "family", "shift", "exp", "supplier", "dtype", "inspection"]
NUMERIC_KEYS = [k for k in COL if k not in TEXT_KEYS and k != "date"]
NONNEG_KEYS = ["size", "sample_n", "sample_def", "defects", "crit", "major", "minor", "scrap_u",
               "rework_u", "shipped", "escaped", "field_def", "complaints", "unit_cost", "price",
               "revenue", "cogs", "prev", "appr", "scrap_c", "rework_c", "warr", "recall",
               "int_fail", "ext_fail", "copq"]
CAP_KEYS = ["cpk", "sample_rate", "delay"]
MODEL_NUM_KEYS = ["age", "size", "cpk", "ramp", "special"]   # known while the batch is running
MODEL_CAT_KEYS = ["plant", "family", "shift", "exp", "supplier"]

THRESHOLDS = {
    "cpk_critical": 1.0,   # below 1.0 the process cannot hold the specification
    "cpk_target": 1.33,    # usual minimum capability agreed with customers
    "delay_days": 3,       # slips beyond three days start to touch delivery terms
}
TERMINOLOGY = {"revenue": "Batch revenue", "customer": "Customer", "product": "Product family",
               "transaction": "Batch"}
CURRENCY = {"code": None, "symbol": ""}
LOCALE = "en-US"
BIGQUERY = {"project_id": "", "dataset": "", "table": "feat", "credentials_file": "credentials.json"}
