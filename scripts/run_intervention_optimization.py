"""Run Step 10 resilience intervention optimization."""

from __future__ import annotations

import argparse
import os
import uuid
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

from src.optimization.interventions import (
    Intervention,
    InterventionConfig,
    evaluate_interventions,
    pareto_frontier,
)
from src.optimization.network import build_cost_matrix, build_road_cost_matrix


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--forecast-date", required=True)
    p.add_argument("--model-version", default="hub-od-xgb-v1")
    p.add_argument("--n-simulations", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--service-target", type=float, default=0.95)
    p.add_argument("--horizon-days", type=int, default=1)
    p.add_argument("--output", default="data/artifacts/intervention_optimization.csv")
    p.add_argument("--no-persist", action="store_true")
    return p.parse_args()


def fetch_all(sb, table, select="*"):
    rows, offset = [], 0
    while True:
        batch = (
            sb.table(table)
            .select(select)
            .range(offset, offset + 999)
            .execute()
            .data
        )
        rows.extend(batch)
        if len(batch) < 1000:
            return pd.DataFrame(rows)
        offset += 1000


def main():
    load_dotenv()
    args = parse_args()
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    forecast = fetch_all(
        sb,
        "logistics_forecast_predictions",
        "forecast_date,origin_hub_id,destination_hub_id,xgb_pred,model_version",
    )
    forecast = forecast[
        (forecast["forecast_date"] == args.forecast_date)
        & (forecast["model_version"] == args.model_version)
    ].copy()
    if forecast.empty:
        raise RuntimeError(
            "No forecast rows found. Run Step 5 first for the requested date/model."
        )

    demand = forecast.rename(
        columns={
            "origin_hub_id": "origin_hub",
            "destination_hub_id": "destination_hub",
            "xgb_pred": "demand",
        }
    )[["origin_hub", "destination_hub", "demand"]]

    hubs = fetch_all(sb, "logistics_hubs")
    capacity = fetch_all(sb, "logistics_hub_capacity")
    hubs = hubs.merge(
        capacity[["hub_id", "capacity_parcels_per_day"]],
        on="hub_id",
        how="left",
    )
    fleet = fetch_all(sb, "logistics_fleet")
    road = fetch_all(sb, "logistics_road_matrix")

    if road.empty:
        route_matrix = build_cost_matrix(hubs)
        print("WARNING: OSRM matrix is empty; using explicit Haversine fallback.")
    else:
        route_matrix = build_road_cost_matrix(road)

    interventions = [
        Intervention(
            "capacity_plus_10pct",
            "hub_capacity",
            variable_cost=8.0,
            capacity_uplift=0.10,
            description="10% network-wide hub capacity uplift",
        ),
        Intervention(
            "capacity_plus_20pct",
            "hub_capacity",
            variable_cost=15.0,
            capacity_uplift=0.20,
            description="20% network-wide hub capacity uplift",
        ),
        Intervention(
            "fleet_plus_10pct",
            "fleet",
            variable_cost=18.0,
            fleet_uplift=0.10,
            description="10% additional operating fleet",
        ),
        Intervention(
            "fleet_plus_20pct",
            "fleet",
            variable_cost=34.0,
            fleet_uplift=0.20,
            description="20% additional operating fleet",
        ),
        Intervention(
            "reserve_fleet_10pct",
            "reserve_fleet",
            fixed_cost=30.0,
            reserve_vehicle_multiplier=0.10,
            description="10% reserve vehicle pool",
        ),
    ]

    cfg = InterventionConfig(
        n_simulations=args.n_simulations,
        seed=args.seed,
        service_target=args.service_target,
        horizon_days=args.horizon_days,
    )
    results = evaluate_interventions(
        demand, hubs, route_matrix, fleet, interventions, config=cfg
    )
    results = pareto_frontier(results)

    run_id = str(uuid.uuid4())
    results["run_id"] = run_id
    results["forecast_date"] = args.forecast_date
    results["model_version"] = args.model_version

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)

    if not args.no_persist:
        result_payload = results[
            [
                "run_id", "intervention_id", "forecast_date", "model_version",
                "intervention_cost", "probability_target_met",
                "service_level_p05", "service_level_p50", "service_level_p95",
                "unmet_demand_p50", "unmet_demand_p95",
                "transport_cost_p50", "transport_cost_cvar95",
                "risk_reduction", "service_p50_uplift", "cost_delta_p50",
                "feasible",
            ]
        ].to_dict("records")
        sb.table("logistics_intervention_results").insert(result_payload).execute()

        frontier_payload = results[
            [
                "run_id", "intervention_id", "intervention_cost",
                "probability_target_met", "service_level_p50",
                "unmet_demand_p95", "transport_cost_p50",
                "feasible", "pareto_efficient",
            ]
        ].to_dict("records")
        sb.table("logistics_intervention_frontier").insert(frontier_payload).execute()

    print(
        results.sort_values(
            ["pareto_efficient", "probability_target_met"],
            ascending=[False, False],
        ).to_string(index=False)
    )


if __name__ == "__main__":
    main()
