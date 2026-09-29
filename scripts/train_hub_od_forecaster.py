"""Train leakage-safe hub-to-hub parcel demand forecasts.

Uses a chronological 28-day holdout. The feature table contains zero-filled
daily OD panels and lag/rolling features computed only from dates before the
prediction date.

Run:
    python scripts/train_hub_od_forecaster.py

Environment:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""
import json, os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from supabase import create_client
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

MODEL_VERSION = os.getenv("MODEL_VERSION", "hub-od-xgb-v1")
PAGE_SIZE = 1000
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts/hub_od_forecast"))
FEATURES = [
    "origin_hub_id","destination_hub_id","lag_1","lag_7","lag_14","lag_28",
    "lag_weight_7","lag_volume_7","rolling_mean_7","rolling_mean_28",
    "rolling_std_28","day_of_week","month_num","day_of_month","day_of_year",
    "route_distance_km"
]

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def fetch_all():
    rows = []
    start = 0
    while True:
        batch = (supabase.table("logistics_hub_od_features")
                 .select("*").order("purchase_date").range(start, start + PAGE_SIZE - 1)
                 .execute().data)
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return pd.DataFrame(rows)


def wape(y, p):
    denom = float(np.abs(y).sum())
    return float(np.abs(y - p).sum() / denom) if denom else 0.0


def evaluate(y, p):
    return {
        "wape": wape(y, p),
        "mae": float(mean_absolute_error(y, p)),
        "rmse": float(np.sqrt(mean_squared_error(y, p))),
    }


def main():
    df = fetch_all()
    df["purchase_date"] = pd.to_datetime(df["purchase_date"])
    for c in FEATURES + ["parcel_count"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=FEATURES + ["parcel_count"]).sort_values("purchase_date")

    train = df[df["split"] == "train"].copy()
    test = df[df["split"] == "test"].copy()

    model = XGBRegressor(
        n_estimators=700, max_depth=7, learning_rate=0.035,
        subsample=0.85, colsample_bytree=0.85, min_child_weight=3,
        reg_alpha=0.05, reg_lambda=1.5, objective="reg:squarederror",
        random_state=42, n_jobs=-1
    )
    model.fit(train[FEATURES], train["parcel_count"])

    pred = np.maximum(model.predict(test[FEATURES]), 0)
    baseline = test["lag_7"].to_numpy()
    y = test["parcel_count"].to_numpy()

    metrics = evaluate(y, pred)
    base_metrics = evaluate(y, baseline)
    metrics.update({
        "model_version": MODEL_VERSION,
        "evaluation_start": test["purchase_date"].min().date().isoformat(),
        "evaluation_end": test["purchase_date"].max().date().isoformat(),
        "baseline_wape": base_metrics["wape"],
        "baseline_mae": base_metrics["mae"],
        "baseline_rmse": base_metrics["rmse"],
        "rows_evaluated": int(len(test)),
    })

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES, "version": MODEL_VERSION}, ARTIFACT_DIR / "model.joblib")
    (ARTIFACT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))

    out = test[["purchase_date","origin_hub_id","destination_hub_id","parcel_count"]].copy()
    out["baseline_pred"] = baseline
    out["xgb_pred"] = pred
    out["forecast_date"] = out.pop("purchase_date").dt.date.astype(str)
    out["actual_parcels"] = out.pop("parcel_count")
    out["model_version"] = MODEL_VERSION
    out = out[["forecast_date","origin_hub_id","destination_hub_id","actual_parcels","baseline_pred","xgb_pred","model_version"]]

    for start in range(0, len(out), 500):
        batch = out.iloc[start:start+500].to_dict("records")
        supabase.table("logistics_forecast_predictions").upsert(
            batch, on_conflict="forecast_date,origin_hub_id,destination_hub_id,model_version"
        ).execute()

    supabase.table("logistics_forecast_metrics").upsert(metrics, on_conflict="model_version").execute()

    improvement = 1 - metrics["wape"] / max(metrics["baseline_wape"], 1e-12)
    print(json.dumps({**metrics, "wape_improvement_vs_lag7": improvement}, indent=2))


if __name__ == "__main__":
    main()
