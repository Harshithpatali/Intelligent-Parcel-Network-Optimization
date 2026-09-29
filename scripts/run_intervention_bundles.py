"""Run Step 10C intervention bundle optimization."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from supabase import create_client

from src.optimization.intervention_bundles import BundleConfig, evaluate_bundle_candidates
from src.optimization.network import build_cost_matrix, build_road_cost_matrix
from src.optimization.targeted_hub_interventions import (
    TargetedInterventionConfig,
    build_targeted_interventions,
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
    p.add_argument("--budget", type=float, default=100.0)
    p.add_argument("--required-reliability", type=float, default=0.90)
    p.add_argument("--service-target", type=float, default=0.95)
    p.add_argument("--max-bundle-size", type=int, default=3)
    p.add_argument("--pilot-simulations", type=int, default=30)
    p.add_argument("--final-candidates", type=int, default=75)
    p.add_argument("--top-hubs", type=int, default=5)
    p.add_argument("--output", default="data/artifacts/intervention_bundles.csv")
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
            "xgb_pred": "demand",
        }
    )[["origin_hub", "destination_hub", "demand"]]

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

    interventions = build_targeted_interventions(
        demand,
        hubs,
        TargetedInterventionConfig(top_hubs=args.top_hubs),
    )

    cfg = BundleConfig(
        n_simulations=args.n_simulations,
        seed=args.seed,
        budget=args.budget,
        service_target=args.service_target,
        required_reliability=args.required_reliability,
        max_bundle_size=args.max_bundle_size,
        pilot_simulations=args.pilot_simulations,
        final_candidate_limit=args.final_candidates,
    )
    print(
        f"Bundle search: {args.n_simulations} full simulations, "
        f"{args.pilot_simulations} pilot simulations, "
        f"max {args.final_candidates} final candidates.",
        flush=True,
    )
    results = evaluate_bundle_candidates(
        demand, hubs, route_matrix, fleet, interventions, cfg
    )

    run_id = str(uuid.uuid4())
    results["run_id"] = run_id
    results["forecast_date"] = args.forecast_date
    results["model_version"] = args.model_version

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)

    if not args.no_persist:
        rows = []
        for row in results.to_dict("records"):
            rows.append({
                "bundle_id": row["bundle_id"],
                "run_id": run_id,
                "forecast_date": args.forecast_date,
                "model_version": args.model_version,
                "budget": args.budget,
                "intervention_cost": row["intervention_cost"],
                "probability_target_met": row["probability_target_met"],
                "service_level_p05": row["service_level_p05"],
                "service_level_p50": row["service_level_p50"],
                "unmet_demand_p95": row["unmet_demand_p95"],
                "transport_cost_p50": row["transport_cost_p50"],
                "transport_cost_cvar95": row["transport_cost_cvar95"],
                "expected_unmet_demand": row["expected_unmet_demand"],
                "objective_value": row["objective_value"],
                "feasible": row["feasible"],
                "pareto_efficient": row["pareto_efficient"],
                "selected_interventions": json.dumps(row["selected_interventions"]),
            })
        sb.table("logistics_intervention_bundles").insert(rows).execute()

    print("\nFEASIBLE BUNDLES")
    print(
        results[results["feasible"]]
        .sort_values(["objective_value", "intervention_cost"])
        .head(20)
        .to_string(index=False)
    )
    print("\nPARETO FRONTIER")
    print(
        results[results["pareto_efficient"]]
        .sort_values("intervention_cost")
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
