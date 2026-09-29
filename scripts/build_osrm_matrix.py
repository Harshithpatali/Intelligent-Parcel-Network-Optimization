"""Build an OSM/OSRM road distance + travel-time matrix for candidate hubs.

Run from a machine/CI runner with outbound HTTPS access:
    python scripts/build_osrm_matrix.py

The OSRM Table service returns fastest-route distance and duration for every
source/destination pair. No straight-line fallback is written by default.
"""
import os, time
from datetime import datetime, timezone

import requests
from supabase import create_client

OSRM_URL = os.getenv("OSRM_URL", "https://router.project-osrm.org")
PROFILE = os.getenv("OSRM_PROFILE", "driving")
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
TIMEOUT = int(os.getenv("OSRM_TIMEOUT_SECONDS", "120"))
RETRIES = int(os.getenv("OSRM_RETRIES", "3"))

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_hubs():
    result = supabase.table("logistics_hubs").select("hub_id,lat,lng").order("hub_id").execute()
    return result.data


def fetch_matrix(hubs):
    coords = ";".join(f"{h['lng']:.7f},{h['lat']:.7f}" for h in hubs)
    url = f"{OSRM_URL.rstrip('/')}/table/v1/{PROFILE}/{coords}"
    params = {"annotations": "duration,distance"}
    last_error = None
    for attempt in range(1, RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != "Ok":
                raise RuntimeError(f"OSRM returned {payload.get('code')}: {payload}")
            return payload
        except Exception as exc:
            last_error = exc
            if attempt < RETRIES:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"OSRM request failed after {RETRIES} attempts") from last_error


def upsert_matrix(hubs, payload):
    distances = payload["distances"]
    durations = payload["durations"]
    queried_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for i, origin in enumerate(hubs):
        for j, destination in enumerate(hubs):
            distance_m = distances[i][j]
            duration_s = durations[i][j]
            if distance_m is None or duration_s is None:
                raise RuntimeError(
                    f"No road route for hub {origin['hub_id']} -> {destination['hub_id']}. "
                    "Investigate the coordinates instead of silently falling back."
                )
            rows.append({
                "origin_hub_id": origin["hub_id"],
                "destination_hub_id": destination["hub_id"],
                "distance_km": float(distance_m) / 1000.0,
                "travel_time_hours": float(duration_s) / 3600.0,
                "routing_engine": "OSRM",
                "profile": PROFILE,
                "queried_at": queried_at,
                "is_fallback": False,
            })
    # Supabase REST payloads are kept reasonably small.
    for start in range(0, len(rows), 100):
        supabase.table("logistics_road_matrix").upsert(
            rows[start:start + 100],
            on_conflict="origin_hub_id,destination_hub_id",
        ).execute()


if __name__ == "__main__":
    hubs = get_hubs()
    if len(hubs) != 20:
        raise RuntimeError(f"Expected 20 candidate hubs, found {len(hubs)}")
    payload = fetch_matrix(hubs)
    upsert_matrix(hubs, payload)
    print(f"Wrote {len(hubs) * len(hubs):,} road-network pairs using {PROFILE} routing.")
