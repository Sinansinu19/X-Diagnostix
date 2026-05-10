import pandas as pd
import joblib
import shap

# --------------------------
# LOAD MODEL
# --------------------------

model = joblib.load("models/xgb_rul_model.pkl")

# --------------------------
# COLUMN NAMES
# --------------------------

columns = ['engine_id', 'cycle', 'op1', 'op2', 'op3']

for i in range(1, 22):
    columns.append(f'sensor_{i}')

# --------------------------
# LOAD DATA
# --------------------------

df = pd.read_csv(
    "data/train_FD001.txt",
    sep=r"\s+",
    header=None
)

df = df.iloc[:, :26]

df.columns = columns

# --------------------------
# REMOVE CONSTANT COLUMNS
# --------------------------

drop_cols = []

for col in df.columns:

    if col not in ['engine_id', 'cycle']:

        if df[col].std() < 0.01:
            drop_cols.append(col)

X = df.drop(columns=drop_cols)

# --------------------------
# SHAP EXPLAINER
# --------------------------

explainer = shap.Explainer(model)

# --------------------------
# SAMPLE
# --------------------------

sample = X.iloc[:100]

# --------------------------
# SHAP VALUES
# --------------------------

shap_values = explainer(sample)

# --------------------------
# SUMMARY PLOT
# --------------------------

shap.summary_plot(shap_values, sample)