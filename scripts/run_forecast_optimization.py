import argparse
import os
import sys
import uuid
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.optimization.network import build_cost_matrix, build_road_cost_matrix, solve_network


def fetch_all(client, table, columns="*"):
    rows, start, page = [], 0, 1000
    while True:
        result = client.table(table).select(columns).range(start, start + page - 1).execute()
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page:
            return pd.DataFrame(rows)
        start += page


def main():
    parser = argparse.ArgumentParser(description="Optimize a forecasted parcel network.")
    parser.add_argument("--forecast-date", default=None)
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--capacity-multiplier", type=float, default=1.0)
    parser.add_argument("--output", default="data/artifacts/optimized_forecast_flows.csv")
    parser.add_argument("--no-persist", action="store_true", help="Do not write optimized flows to Supabase")
    args = parser.parse_args()

    load_dotenv()
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    client = create_client(url, key)

    hubs = fetch_all(client, "logistics_hubs", "hub_id,lat,lng")
    capacity = fetch_all(client, "logistics_hub_capacity")
    fleet = fetch_all(client, "logistics_fleet")
    forecast = fetch_all(
        client,
        "logistics_forecast_predictions",
        "forecast_date,origin_hub_id,destination_hub_id,xgb_pred,model_version",
    )

    if forecast.empty:
        raise RuntimeError(
            "No forecast predictions found. Run scripts/train_hub_od_forecaster.py first."
        )

    forecast["forecast_date"] = pd.to_datetime(forecast["forecast_date"]).dt.date
    if args.forecast_date:
        target_date = pd.to_datetime(args.forecast_date).date()
    else:
        target_date = forecast["forecast_date"].max()

    forecast = forecast[forecast.forecast_date == target_date].copy()
    if args.model_version:
        forecast = forecast[forecast.model_version == args.model_version].copy()
    elif not forecast.empty:
        latest_version = forecast.sort_values("model_version").model_version.iloc[-1]
        forecast = forecast[forecast.model_version == latest_version].copy()

    if forecast.empty:
        raise RuntimeError("No forecast rows match the requested date/model version.")

    hubs = hubs.merge(
        capacity[["hub_id", "capacity_parcels"]],
        on="hub_id",
        how="left",
        validate="one_to_one",
    )
    if hubs.capacity_parcels.isna().any():
        raise RuntimeError("Missing calibrated capacity for one or more hubs.")

    demand = forecast.rename(
        columns={
            "origin_hub_id": "origin_hub",
            "destination_hub_id": "destination_hub",
            "xgb_pred": "parcel_count",
        }
    )[["origin_hub", "destination_hub", "parcel_count"]]

    road = fetch_all(
        client,
        "logistics_road_matrix",
        "origin_hub_id,destination_hub_id,distance_km,travel_time_hours",
    )
    if road.empty:
        print("WARNING: logistics_road_matrix is empty; using analytical Haversine fallback.")
        cost = build_cost_matrix(hubs)
        routing_source = "haversine_fallback"
    else:
        cost = build_road_cost_matrix(road)
        routing_source = "osrm"

    flows, metrics = solve_network(
        demand=demand,
        hubs=hubs,
        cost=cost,
        capacity_multiplier=args.capacity_multiplier,
        fleet=fleet,
    )

    run_id = str(uuid.uuid4())
    flows["forecast_date"] = str(target_date)
    flows["model_version"] = forecast.model_version.iloc[0]
    flows["run_id"] = run_id

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    flows.to_csv(out, index=False)

    if not args.no_persist and not flows.empty:
        persist_cols = [
            "run_id", "forecast_date", "origin_hub", "destination_hub",
            "vehicle_type", "requested_parcels", "parcels", "unmet_parcels",
            "trips", "distance_km", "travel_time_hours", "transport_cost",
            "model_version",
        ]
        client.table("logistics_optimized_flows").insert(
            flows[persist_cols].where(pd.notna(flows[persist_cols]), None).to_dict("records")
        ).execute()

    print({
        "run_id": run_id,
        "forecast_date": str(target_date),
        "model_version": forecast.model_version.iloc[0],
        "routing_source": routing_source,
        **metrics,
    })
    print(f"Saved {len(flows)} optimized flow rows to {out}")


if __name__ == "__main__":
    main()
