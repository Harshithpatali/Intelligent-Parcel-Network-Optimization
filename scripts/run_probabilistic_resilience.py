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
from src.optimization.probabilistic import (
    SimulationConfig,
    run_probabilistic_simulation,
    summarize_risk,
)


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
    parser = argparse.ArgumentParser(description="Run probabilistic resilience simulation.")
    parser.add_argument("--forecast-date", default=None)
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--n-simulations", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--service-target", type=float, default=0.95)
    parser.add_argument("--hub-failure-probability", type=float, default=0.05)
    parser.add_argument("--route-failure-probability", type=float, default=0.02)
    parser.add_argument("--output", default="data/artifacts/probabilistic_resilience.csv")
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

    config = SimulationConfig(
        n_simulations=args.n_simulations,
        seed=args.seed,
        service_level_target=args.service_target,
        hub_failure_probability=args.hub_failure_probability,
        route_failure_probability=args.route_failure_probability,
    )

    results = run_probabilistic_simulation(
        demand=demand,
        hubs=hubs,
        fleet=fleet,
        cost=cost,
        config=config,
    )
    results["forecast_date"] = str(target_date)
    results["model_version"] = forecast.model_version.iloc[0]
    results["routing_source"] = routing_source

    summary = summarize_risk(results, args.service_target)
    summary["summary_id"] = str(uuid.uuid4())
    summary["forecast_date"] = str(target_date)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out, index=False)

    if not args.no_persist:
        rows = results[[
            "forecast_date", "seed", "demand_multiplier"
        ]] if False else None

        # Simulation-level persistence is inserted in chunks to avoid oversized requests.
        records = results[[
            "scenario_name", "forecast_date", "demand_multiplier",
            "capacity_multiplier", "fleet_multiplier", "hub_failures",
            "road_failures", "service_level", "unmet_demand",
            "total_transport_cost", "objective_with_unmet_penalty",
            "target_met"
        ]].copy()
        records["simulation_id"] = [str(uuid.uuid4()) for _ in range(len(records))]
        records["simulation_seed"] = args.seed
        cols = [
            "simulation_id", "forecast_date", "simulation_seed",
            "demand_multiplier", "capacity_multiplier", "fleet_multiplier",
            "hub_failures", "road_failures", "service_level",
            "unmet_demand", "total_transport_cost",
            "objective_with_unmet_penalty", "target_service_level",
            "target_met"
        ]
        records["target_service_level"] = args.service_target
        payload = records[cols].where(pd.notna(records[cols]), None).to_dict("records")
        for start in range(0, len(payload), 100):
            client.table("logistics_resilience_simulations").insert(
                payload[start:start + 100]
            ).execute()

        client.table("logistics_resilience_risk_summary").insert({
            **summary
        }).execute()

    print("Probabilistic resilience simulation")
    print(f"Simulations: {len(results)}")
    print(f"Target service level: {args.service_target:.1%}")
    print(f"Probability target met: {summary['probability_target_met']:.2%}")
    print(f"Service level P05/P50/P95: "
          f"{summary['service_level_p05']:.4f} / "
          f"{summary['service_level_p50']:.4f} / "
          f"{summary['service_level_p95']:.4f}")
    print(f"Unmet demand P50/P95: "
          f"{summary['unmet_demand_p50']:.2f} / "
          f"{summary['unmet_demand_p95']:.2f}")
    print(f"Transport cost P50/P95: "
          f"{summary['transport_cost_p50']:.2f} / "
          f"{summary['transport_cost_p95']:.2f}")
    print(f"VaR95 / CVaR95: "
          f"{summary['transport_cost_var95']:.2f} / "
          f"{summary['transport_cost_cvar95']:.2f}")
    print(f"Saved simulation results to {out}")


if __name__ == "__main__":
    main()
