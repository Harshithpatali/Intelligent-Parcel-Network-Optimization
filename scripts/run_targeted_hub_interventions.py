"""Run targeted hub resilience interventions."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

from src.optimization.network import build_cost_matrix, build_road_cost_matrix
from src.optimization.targeted_hub_interventions import (
    TargetedInterventionConfig,
    build_targeted_interventions,
    evaluate_targeted_interventions,
)


def fetch_all(sb, table, select="*"):
    rows, offset = [], 0
    while True:
        batch = sb.table(table).select(select).range(offset, offset + 999).execute().data
        rows.extend(batch)
        if len(batch) < 1000:
            return pd.DataFrame(rows)
        offset += 1000


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--forecast-date", required=True)
    p.add_argument("--model-version", default="hub-od-xgb-v1")
    p.add_argument("--n-simulations", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--service-target", type=float, default=0.95)
    p.add_argument("--top-hubs", type=int, default=5)
    p.add_argument("--output", default="data/artifacts/targeted_interventions.csv")
    p.add_argument("--no-persist", action="store_true")
    args = p.parse_args()

    load_dotenv()
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    forecast = fetch_all(
        sb, "logistics_forecast_predictions",
        "forecast_date,origin_hub_id,destination_hub_id,xgb_pred,model_version",
    )
    forecast = forecast[
        (forecast["forecast_date"] == args.forecast_date)
        & (forecast["model_version"] == args.model_version)
    ]
    if forecast.empty:
        raise RuntimeError("No forecast rows found for the requested date/model.")

    demand = forecast.rename(
        columns={
            "origin_hub_id": "origin_hub",
            "destination_hub_id": "destination_hub",
            "xgb_pred": "parcel_count",
        }
    )[["origin_hub", "destination_hub", "parcel_count"]]

    hubs = fetch_all(sb, "logistics_hubs")
    capacity = fetch_all(sb, "logistics_hub_capacity")
    hubs = hubs.merge(
        capacity[["hub_id", "capacity_parcels"]],
        on="hub_id",
        how="left",
    )

    fleet = fetch_all(sb, "logistics_fleet")
    road = fetch_all(sb, "logistics_road_matrix")
    route_matrix = build_road_cost_matrix(road) if not road.empty else build_cost_matrix(hubs)

    if road.empty:
        print("WARNING: OSRM matrix is empty; using explicit Haversine fallback.")

    cfg = TargetedInterventionConfig(top_hubs=args.top_hubs)
    hub_rank, results = evaluate_targeted_interventions(
        demand, hubs, route_matrix, fleet, cfg,
        n_simulations=args.n_simulations,
        seed=args.seed,
        service_target=args.service_target,
    )

    run_id = str(uuid.uuid4())
    results["run_id"] = run_id
    results["forecast_date"] = args.forecast_date
    results["model_version"] = args.model_version

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)
    hub_rank.to_csv("data/artifacts/targeted_hub_ranking.csv", index=False)

    if not args.no_persist:
        candidates = build_targeted_interventions(demand, hubs, cfg)
        plans = [{
            "intervention_id": i.intervention_id,
            "intervention_type": i.intervention_type,
            "target_hub_id": i.target_hub_id,
            "parameter_name": "capacity_uplift",
            "parameter_value": i.capacity_uplift,
            "fixed_cost": i.fixed_cost,
            "variable_cost": i.variable_cost,
            "description": i.description,
        } for i in candidates]
        sb.table("logistics_intervention_plans").upsert(
            plans, on_conflict="intervention_id"
        ).execute()

        rows = results[
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
        sb.table("logistics_intervention_results").insert(rows).execute()

        frontier = results[
            [
                "run_id", "intervention_id", "intervention_cost",
                "probability_target_met", "service_level_p50",
                "unmet_demand_p95", "transport_cost_p50",
                "feasible", "pareto_efficient",
            ]
        ].to_dict("records")
        sb.table("logistics_intervention_frontier").insert(frontier).execute()

    print("\nTARGETED HUB RANKING")
    print(hub_rank.to_string(index=False))
    print("\nTARGETED INTERVENTION FRONTIER")
    print(
        results[results["pareto_efficient"]]
        .sort_values("probability_target_met", ascending=False)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
