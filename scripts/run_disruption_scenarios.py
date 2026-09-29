import argparse
import os
import sys
import uuid
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.optimization.network import build_cost_matrix, build_road_cost_matrix
from src.optimization.scenarios import standard_scenarios, run_scenario


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
    parser = argparse.ArgumentParser(description="Run disruption scenarios against a forecasted parcel network.")
    parser.add_argument("--forecast-date", default=None)
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--output", default="data/artifacts/scenario_results.csv")
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    hubs = fetch_all(client, "logistics_hubs", "hub_id,lat,lng")
    capacity = fetch_all(client, "logistics_hub_capacity")
    fleet = fetch_all(client, "logistics_fleet")
    forecast = fetch_all(
        client,
        "logistics_forecast_predictions",
        "forecast_date,origin_hub_id,destination_hub_id,xgb_pred,model_version",
    )
    road = fetch_all(
        client,
        "logistics_road_matrix",
        "origin_hub_id,destination_hub_id,distance_km,travel_time_hours",
    )

    if forecast.empty:
        raise RuntimeError("No forecast predictions found. Train the Step 5 forecaster first.")

    forecast["forecast_date"] = pd.to_datetime(forecast["forecast_date"]).dt.date
    target_date = (
        pd.to_datetime(args.forecast_date).date()
        if args.forecast_date
        else forecast.forecast_date.max()
    )
    forecast = forecast[forecast.forecast_date == target_date].copy()

    if args.model_version:
        forecast = forecast[forecast.model_version == args.model_version].copy()
    elif not forecast.empty:
        latest = forecast.sort_values("model_version").model_version.iloc[-1]
        forecast = forecast[forecast.model_version == latest].copy()

    if forecast.empty:
        raise RuntimeError("No forecast rows match the requested date/model.")

    hubs = hubs.merge(
        capacity[["hub_id", "capacity_parcels"]],
        on="hub_id",
        how="left",
        validate="one_to_one",
    )
    if hubs.capacity_parcels.isna().any():
        raise RuntimeError("Missing capacity calibration.")

    demand = forecast.rename(
        columns={
            "origin_hub_id": "origin_hub",
            "destination_hub_id": "destination_hub",
            "xgb_pred": "parcel_count",
        }
    )[["origin_hub", "destination_hub", "parcel_count"]]

    if road.empty:
        cost = build_cost_matrix(hubs)
        routing_source = "haversine_fallback"
    else:
        cost = build_road_cost_matrix(road)
        routing_source = "osrm"

    scenarios = standard_scenarios(hubs, cost)
    baseline = None
    results = []
    flow_rows = []

    for scenario in scenarios:
        flows, metrics = run_scenario(demand, hubs, fleet, cost, scenario)
        run_id = str(uuid.uuid4())
        metrics["run_id"] = run_id
        metrics["forecast_date"] = str(target_date)
        metrics["model_version"] = forecast.model_version.iloc[0]
        metrics["routing_source"] = routing_source

        if scenario.name == "baseline":
            baseline = metrics.copy()

        if baseline is not None:
            metrics["baseline_cost"] = baseline["total_transport_cost"]
            metrics["incremental_cost"] = (
                metrics["total_transport_cost"] - baseline["total_transport_cost"]
            )
            metrics["incremental_unmet_demand"] = (
                metrics["unmet_demand"] - baseline["unmet_demand"]
            )

        results.append(metrics)

        if not flows.empty:
            flows["run_id"] = run_id
            flows["forecast_date"] = str(target_date)
            flows["scenario_name"] = scenario.name
            flow_rows.append(flows)

    result_df = pd.DataFrame(results)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(out, index=False)

    if not args.no_persist:
        scenario_map = fetch_all(client, "logistics_disruption_scenarios")
        for row in results:
            existing = scenario_map[scenario_map.scenario_name == row["scenario"]]
            scenario_id = existing.scenario_id.iloc[0] if not existing.empty else None
            payload = {
                "run_id": row["run_id"],
                "scenario_id": scenario_id,
                "forecast_date": row["forecast_date"],
                "scenario_name": row["scenario"],
                "scenario_type": row["scenario_type"],
                "routing_source": row["routing_source"],
                "model_version": row["model_version"],
                "total_requested": row.get("total_requested", row.get("total_parcels")),
                "total_parcels": row.get("total_parcels"),
                "unmet_demand": row.get("unmet_demand"),
                "service_level": row.get("service_level"),
                "total_transport_cost": row.get("total_transport_cost"),
                "objective_with_unmet_penalty": row.get("objective_with_unmet_penalty"),
                "baseline_cost": row.get("baseline_cost"),
                "incremental_cost": row.get("incremental_cost"),
                "incremental_unmet_demand": row.get("incremental_unmet_demand"),
            }
            client.table("logistics_scenario_results").insert(payload).execute()

        if flow_rows:
            all_flows = pd.concat(flow_rows, ignore_index=True)
            cols = [
                "run_id", "forecast_date", "scenario_name", "origin_hub",
                "destination_hub", "vehicle_type", "requested_parcels",
                "parcels", "unmet_parcels", "trips", "distance_km",
                "travel_time_hours", "transport_cost",
            ]
            client.table("logistics_scenario_flows").insert(
                all_flows[cols].where(pd.notna(all_flows[cols]), None).to_dict("records")
            ).execute()

    print(result_df[[
        "scenario", "scenario_type", "service_level",
        "unmet_demand", "total_transport_cost",
        "incremental_cost", "incremental_unmet_demand"
    ]].to_string(index=False))
    print(f"Saved scenario results to {out}")


if __name__ == "__main__":
    main()
