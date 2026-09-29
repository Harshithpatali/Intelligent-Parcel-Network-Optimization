import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.optimization.network import build_cost_matrix, build_road_cost_matrix
from src.optimization.resilience import FrontierConfig, run_resilience_frontier


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
    parser = argparse.ArgumentParser(description="Search the parcel network resilience frontier.")
    parser.add_argument("--forecast-date", default=None)
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--service-target", type=float, default=0.95)
    parser.add_argument("--output", default="data/artifacts/resilience_frontier.csv")
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

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
        raise RuntimeError("Missing calibrated capacity.")

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

    config = FrontierConfig(service_level_target=args.service_target)
    result = run_resilience_frontier(
        demand=demand,
        hubs=hubs,
        fleet=fleet,
        cost=cost,
        config=config,
    )
    result["forecast_date"] = str(target_date)
    result["model_version"] = forecast.model_version.iloc[0]
    result["routing_source"] = routing_source

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False)

    if not args.no_persist:
        persist_cols = [
            "run_id", "forecast_date", "scenario_name",
            "demand_multiplier", "capacity_multiplier", "fleet_multiplier",
            "service_level", "unmet_demand", "total_transport_cost",
            "objective_with_unmet_penalty", "feasible_target",
            "service_level_target", "intervention_score",
        ]
        client.table("logistics_resilience_frontier").insert(
            result[persist_cols].where(pd.notna(result[persist_cols]), None).to_dict("records")
        ).execute()

    feasible = result[result.feasible_target]
    pareto = result[result.pareto_frontier]

    print(f"Evaluated {len(result)} resilience scenarios.")
    print(f"Scenarios meeting {args.service_target:.1%} service: {len(feasible)}")
    print(f"Pareto frontier points: {len(pareto)}")

    if not feasible.empty:
        best = feasible.sort_values(
            ["intervention_score", "total_transport_cost"],
            ascending=[True, True],
        ).iloc[0]
        print({
            "minimum_intervention_candidate": best.scenario_name,
            "demand_multiplier": best.demand_multiplier,
            "capacity_multiplier": best.capacity_multiplier,
            "fleet_multiplier": best.fleet_multiplier,
            "service_level": best.service_level,
            "transport_cost": best.total_transport_cost,
        })

    print(f"Saved resilience frontier to {out}")


if __name__ == "__main__":
    main()
