from __future__ import annotations
import argparse
import os, uuid
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

from src.analytics.root_cause import analyze_simulations, hub_pressure_table


def fetch_all(sb, table, select="*"):
    rows = []
    offset = 0
    while True:
        batch = sb.table(table).select(select).range(offset, offset + 999).execute().data
        rows.extend(batch)
        if len(batch) < 1000:
            return pd.DataFrame(rows)
        offset += 1000


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-simulations", type=int, default=500)
    parser.add_argument("--forecast-date", default=None)
    args = parser.parse_args()

    if args.n_simulations < 1:
        raise ValueError("--n-simulations must be >= 1")

    load_dotenv()
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    sims = fetch_all(sb, "logistics_resilience_simulations")
    if sims.empty:
        raise RuntimeError("No resilience simulations available.")
    sims["created_at"] = pd.to_datetime(sims["created_at"])
    if args.forecast_date and "forecast_date" in sims.columns:
        sims["forecast_date"] = pd.to_datetime(sims["forecast_date"]).dt.date
        target_date = pd.to_datetime(args.forecast_date).date()
        sims = sims[sims["forecast_date"] == target_date].copy()
        if sims.empty:
            raise RuntimeError(f"No resilience simulations found for {target_date}.")
    latest = sims.sort_values("created_at", ascending=False).head(args.n_simulations).sort_values("created_at")
    if len(latest) < args.n_simulations:
        raise RuntimeError(
            f"Requested {args.n_simulations} simulations but only {len(latest)} are available."
        )

    run_id = str(uuid.uuid4())
    rows, summary = analyze_simulations(latest, run_id)
    sb.table("logistics_resilience_root_cause").insert(rows.to_dict("records")).execute()

    hubs = fetch_all(sb, "logistics_hubs")
    capacity = fetch_all(sb, "logistics_hub_capacity")
    forecast = fetch_all(sb, "logistics_forecast_predictions")
    pressure = pd.DataFrame()

    if not forecast.empty:
        # Build a clean capacity-enriched hub frame. Do not merge the full
        # logistics_hubs frame because a future schema may already contain a
        # capacity_parcels column, which would create capacity_parcels_x/y.
        hub_ids = hubs[["hub_id"]].drop_duplicates().copy()
        capacity_map = capacity[["hub_id", "capacity_parcels"]].drop_duplicates("hub_id")
        hubs = hub_ids.merge(capacity_map, on="hub_id", how="left")
        if hubs["capacity_parcels"].isna().any():
            missing = hubs.loc[hubs["capacity_parcels"].isna(), "hub_id"].tolist()
            raise RuntimeError(f"Missing calibrated capacity for hubs: {missing}")

        forecast["forecast_date"] = pd.to_datetime(forecast["forecast_date"])
        forecast = (
            forecast.sort_values("forecast_date")
            .groupby(["origin_hub_id", "destination_hub_id"], as_index=False)
            .tail(1)
        )
        demand = forecast.rename(
            columns={
                "origin_hub_id": "origin_hub",
                "destination_hub_id": "destination_hub",
                "xgb_pred": "demand",
            }
        )[["origin_hub", "destination_hub", "demand"]]

        pressure = hub_pressure_table(demand, hubs)
        Path("data/artifacts").mkdir(parents=True, exist_ok=True)
        pressure.to_csv("data/artifacts/hub_capacity_pressure.csv", index=False)

    Path("data/artifacts").mkdir(parents=True, exist_ok=True)
    rows.to_csv("data/artifacts/resilience_root_cause.csv", index=False)

    print("ROOT CAUSE SUMMARY")
    print(summary)
    print("TOP HUB PRESSURE")
    print(pressure.head(10).to_string(index=False) if not pressure.empty else "No forecast rows")


if __name__ == "__main__":
    main()
