"""Final gate for deployment after the full production analytics pipeline.

This gate intentionally validates fresh analytics written by the current run
window instead of merely checking that historical tables are non-empty.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from supabase import create_client


def count(client, table, filters=None):
    q=client.table(table).select("*", count="exact", head=True)
    for column, value in (filters or {}).items():
        q=q.eq(column,value)
    return int(q.execute().count or 0)


def latest_created(client, table, filters=None):
    q=client.table(table).select("created_at").order("created_at", desc=True).limit(1)
    for column, value in (filters or {}).items():
        q=q.eq(column,value)
    rows=q.execute().data or []
    return datetime.fromisoformat(rows[0]["created_at"].replace("Z","+00:00")) if rows else None


def main():
    url=os.environ.get("SUPABASE_URL")
    key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    forecast_date=os.environ.get("FORECAST_DATE")
    model_version=os.environ.get("MODEL_VERSION")
    expected_simulations=int(os.environ.get("SIMULATIONS","500"))
    if not all([url,key,forecast_date,model_version]):
        raise SystemExit("Missing SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, FORECAST_DATE, or MODEL_VERSION.")

    sb=create_client(url,key)
    failures=[]

    if count(sb,"logistics_hubs") != 20:
        failures.append("candidate hub count is not 20")
    if count(sb,"logistics_hub_capacity") != 20:
        failures.append("hub capacity calibration is incomplete")
    if count(sb,"logistics_fleet") < 1:
        failures.append("fleet configuration is missing")
    if count(sb,"logistics_road_matrix") < 400:
        failures.append("road matrix is incomplete")
    if count(sb,"logistics_forecast_predictions",{"forecast_date":forecast_date,"model_version":model_version}) < 264:
        failures.append("forecast predictions are incomplete for the requested date/model")

    scenario_count=count(sb,"logistics_scenario_results",{"forecast_date":forecast_date,"model_version":model_version})
    if scenario_count < 6:
        failures.append(f"expected at least 6 disruption scenarios, found {scenario_count}")

    sim_filters={"forecast_date":forecast_date}
    sim_count=count(sb,"logistics_resilience_simulations",sim_filters)
    if sim_count < expected_simulations:
        failures.append(f"expected at least {expected_simulations} resilience simulations, found {sim_count}")

    now=datetime.now(timezone.utc)
    freshness_limit=now-timedelta(minutes=180)
    for table in [
        "logistics_resilience_risk_summary",
        "logistics_resilience_root_cause",
        "logistics_intervention_bundles",
    ]:
        created=latest_created(sb,table)
        if created is None:
            failures.append(f"{table} has no rows")
        elif created < freshness_limit:
            failures.append(f"{table} is stale: latest row {created.isoformat()}")

    root_latest=sb.table("logistics_resilience_root_cause").select("run_id").order("created_at",desc=True).limit(1).execute().data or []
    if not root_latest:
        failures.append("root-cause decomposition is missing")
    else:
        root_rows=count(sb,"logistics_resilience_root_cause",{"run_id":root_latest[0]["run_id"]})
        if root_rows < 5:
            failures.append(f"root-cause decomposition is incomplete: {root_rows} rows")

    bundle_latest=sb.table("logistics_intervention_bundles").select("run_id").order("created_at",desc=True).limit(1).execute().data or []
    if not bundle_latest:
        failures.append("intervention bundle optimization is missing")
    else:
        bundle_rows=count(sb,"logistics_intervention_bundles",{"run_id":bundle_latest[0]["run_id"]})
        if bundle_rows < 1:
            failures.append("latest intervention bundle run has no persisted results")

    print("Final production gate:")
    print(f"  forecast: {forecast_date} / {model_version}")
    print(f"  resilience simulations: {sim_count}")
    print(f"  disruption scenarios: {scenario_count}")
    print(f"  root-cause rows: {root_rows if root_latest else 0}")
    print(f"  latest bundle rows: {bundle_rows if bundle_latest else 0}")

    if failures:
        print("\nBLOCKED:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)

    print("\nREADY: full analytics pipeline is populated and fresh.")


if __name__ == "__main__":
    main()
