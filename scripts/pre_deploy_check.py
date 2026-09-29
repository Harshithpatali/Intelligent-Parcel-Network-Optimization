"""Fail-fast production data readiness check.

Run after external OSRM routing and forecast training, before deployment.
"""
import os
from pathlib import Path
from supabase import create_client

EXPECTED_HUBS = 20
EXPECTED_ROAD_PAIRS = EXPECTED_HUBS * EXPECTED_HUBS
MODEL_VERSION = os.getenv("MODEL_VERSION", "hub-od-xgb-v1")
FORECAST_DATE = os.getenv("FORECAST_DATE")


def count(sb, table):
    result = sb.table(table).select("*", count="exact", head=True).execute()
    return int(result.count or 0)


def main():
    required = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    missing = [x for x in required if not os.getenv(x)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    checks = {
        "hubs": count(sb, "logistics_hubs"),
        "road_matrix": count(sb, "logistics_road_matrix"),
        "forecast_predictions": count(sb, "logistics_forecast_predictions"),
        "hub_capacity": count(sb, "logistics_hub_capacity"),
        "fleet": count(sb, "logistics_fleet"),
    }

    failures = []
    if checks["hubs"] != EXPECTED_HUBS:
        failures.append(f"expected {EXPECTED_HUBS} hubs, found {checks['hubs']}")
    if checks["road_matrix"] < EXPECTED_ROAD_PAIRS:
        failures.append(f"expected at least {EXPECTED_ROAD_PAIRS} road pairs, found {checks['road_matrix']}")
    if checks["forecast_predictions"] == 0:
        failures.append("no forecast predictions found")
    if checks["hub_capacity"] != EXPECTED_HUBS:
        failures.append(f"expected {EXPECTED_HUBS} hub capacity rows, found {checks['hub_capacity']}")
    if checks["fleet"] == 0:
        failures.append("synthetic fleet configuration is missing")

    if FORECAST_DATE:
        rows = (
            sb.table("logistics_forecast_predictions")
            .select("forecast_date")
            .eq("forecast_date", FORECAST_DATE)
            .eq("model_version", MODEL_VERSION)
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            failures.append(f"no predictions for {FORECAST_DATE} / {MODEL_VERSION}")

    print("Production readiness:")
    for key, value in checks.items():
        print(f"  {key}: {value}")

    if failures:
        print("\nBLOCKED:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)

    artifact = Path("artifacts/hub_od_forecast/model.joblib")
    if not artifact.exists():
        print("\nWARNING: local forecast artifact is absent; deployment can use the persisted predictions, but retraining is not reproducible from this image.")

    print("\nREADY: production data prerequisites are populated.")


if __name__ == "__main__":
    main()
