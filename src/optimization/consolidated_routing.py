from __future__ import annotations

from dataclasses import dataclass
import itertools
import math
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ConsolidatedRouteConfig:
    vehicle_type: str = "linehaul_truck"
    parcel_capacity: int = 40
    max_route_hours: float = 16.0
    fixed_trip_cost: float = 45.0
    cost_per_km: float = 0.075
    max_stops: int = 5
    vehicle_count: int = 10
    operating_hours_per_day: float = 16.0
    distance_weight: float = 0.4
    time_weight: float = 0.4
    economic_weight: float = 0.2
    service_time_minutes_per_stop: float = 15.0

    # Real-world physical constraints.
    max_weight_kg: float = 12000.0
    max_volume_m3: float = 65.0
    loading_minutes: float = 30.0
    unloading_minutes_per_parcel: float = 0.5
    driver_break_hours: float = 0.5
    return_to_origin: bool = False
    empty_return_factor: float = 0.35
    max_detour_pct: float = 25.0
    max_time_detour_pct: float = 25.0
    min_capacity_utilization: float = 0.60

    # Operational control rules.
    origin_cutoff_hour: float = 18.0
    stop_cutoff_hour: float = 23.0
    staging_buffer_hours: float = 0.5


def _hub_key(value: Any) -> str:
    if pd.isna(value):
        return "<NA>"
    return str(value).strip()


def _route_lookup(cost: pd.DataFrame) -> dict[tuple[str, str], dict[str, float]]:
    required = {"origin_hub", "destination_hub", "distance_km", "travel_time_hours"}
    missing = required - set(cost.columns)
    if missing:
        raise ValueError(f"Cost matrix missing columns: {sorted(missing)}")

    lookup: dict[tuple[str, str], dict[str, float]] = {}
    for row in cost.itertuples(index=False):
        lookup[(_hub_key(row.origin_hub), _hub_key(row.destination_hub))] = {
            "distance_km": float(row.distance_km),
            "travel_time_hours": float(row.travel_time_hours),
        }
    return lookup


def _chunks(quantity: float, capacity: int) -> list[float]:
    remaining = float(quantity)
    out: list[float] = []
    while remaining > 1e-9:
        take = min(float(capacity), remaining)
        out.append(take)
        remaining -= take
    return out


def _travel(lookup, origin, destination):
    return lookup.get((_hub_key(origin), _hub_key(destination)))


def _parcel_profile(
    demand: pd.DataFrame,
    origin: Any,
    destination: Any,
    quantity: float,
) -> dict[str, float]:
    """Return physically meaningful load estimates for an OD movement.

    The aggregate routing API accepts demand at OD level, so parcel dimensions
    are estimated from observed parcel-level fields when available. When they
    are not present, conservative planning averages are used.
    """
    subset = demand[
        demand["origin_hub"].map(_hub_key).eq(_hub_key(origin))
        & demand["destination_hub"].map(_hub_key).eq(_hub_key(destination))
    ]

    if "weight_kg" in subset.columns and len(subset):
        avg_weight = float(pd.to_numeric(subset["weight_kg"], errors="coerce").mean())
        avg_weight = avg_weight if math.isfinite(avg_weight) and avg_weight > 0 else 2.5
    else:
        avg_weight = 2.5

    if "volume_m3" in subset.columns and len(subset):
        avg_volume = float(pd.to_numeric(subset["volume_m3"], errors="coerce").mean())
        avg_volume = avg_volume if math.isfinite(avg_volume) and avg_volume > 0 else 0.012
    else:
        avg_volume = 0.012

    return {
        "weight_kg": float(quantity) * avg_weight,
        "volume_m3": float(quantity) * avg_volume,
        "avg_weight_kg": avg_weight,
        "avg_volume_m3": avg_volume,
    }


def _sequence_metrics(origin, sequence, lookup, config: ConsolidatedRouteConfig):
    drive_distance = 0.0
    drive_hours = 0.0
    current = origin
    for destination in sequence:
        leg = _travel(lookup, current, destination)
        if leg is None:
            return None
        drive_distance += leg["distance_km"]
        drive_hours += leg["travel_time_hours"]
        current = destination

    service_hours = (
        config.loading_minutes / 60.0
        + len(sequence) * config.service_time_minutes_per_stop / 60.0
    )
    return drive_distance, drive_hours, drive_hours + service_hours


def _direct_baseline(origin, stops, lookup, config: ConsolidatedRouteConfig):
    distance = 0.0
    drive_time = 0.0
    for destination in stops:
        leg = _travel(lookup, origin, destination)
        if leg is None:
            return None
        distance += leg["distance_km"]
        drive_time += leg["travel_time_hours"]

    # Each direct dispatch includes its own loading cycle and stop handling.
    service_hours = len(stops) * (
        config.loading_minutes / 60.0 + config.service_time_minutes_per_stop / 60.0
    )
    return distance, drive_time, drive_time + service_hours


def _detour_evaluation(origin, sequence, lookup, config: ConsolidatedRouteConfig):
    route = _sequence_metrics(origin, sequence, lookup, config)
    baseline = _direct_baseline(origin, sequence, lookup, config)
    if route is None or baseline is None:
        return None

    route_distance, route_drive_time, route_time = route
    base_distance, base_drive_time, base_time = baseline

    distance_ratio = route_distance / max(base_distance, 1e-9)
    time_ratio = route_time / max(base_time, 1e-9)

    direct_cost = (
        len(sequence) * config.fixed_trip_cost
        + config.cost_per_km * base_distance
    )
    route_cost = config.fixed_trip_cost + config.cost_per_km * route_distance

    return {
        "distance_km": route_distance,
        "travel_time_hours": route_time,
        "drive_time_hours": route_drive_time,
        "baseline_distance_km": base_distance,
        "baseline_time_hours": base_time,
        "distance_ratio": distance_ratio,
        "time_ratio": time_ratio,
        "direct_dispatch_cost": direct_cost,
        "transport_cost": route_cost,
        "estimated_savings": direct_cost - route_cost,
        "estimated_savings_pct": 100.0 * (direct_cost - route_cost) / max(direct_cost, 1e-9),
        "distance_detour_pct": (distance_ratio - 1.0) * 100.0,
        "time_detour_pct": (time_ratio - 1.0) * 100.0,
        "detour_score": (
            config.distance_weight * distance_ratio
            + config.time_weight * time_ratio
            + config.economic_weight * route_cost / max(direct_cost, 1e-9)
        ),
    }


def _best_stop_sequence(origin, stops, lookup, config: ConsolidatedRouteConfig):
    best = None
    for sequence in itertools.permutations(stops):
        evaluation = _detour_evaluation(origin, sequence, lookup, config)
        if evaluation is None:
            continue

        if evaluation["distance_detour_pct"] > config.max_detour_pct + 1e-9:
            continue
        if evaluation["time_detour_pct"] > config.max_time_detour_pct + 1e-9:
            continue

        candidate = (
            evaluation["detour_score"],
            evaluation["economic_ratio"],
            evaluation["distance_km"],
            evaluation["travel_time_hours"],
            tuple(str(x) for x in sequence),
            sequence,
            evaluation,
        )
        if best is None or candidate[:5] < best[:5]:
            best = candidate

    if best is None:
        return None

    evaluation = best[6].copy()
    evaluation["sequence"] = list(best[5])
    return evaluation


def _build_route(origin, first_chunk, chunks, lookup, config, parcel_profiles):
    stops = [first_chunk["destination"]]
    stop_loads = [float(first_chunk["quantity"])]

    def current_load():
        return sum(stop_loads)

    while len(stops) < config.max_stops:
        candidates = []
        for idx, chunk in enumerate(chunks):
            quantity = float(chunk["quantity"])
            if current_load() + quantity > config.parcel_capacity + 1e-9:
                continue

            trial_stops = stops + [chunk["destination"]]
            evaluation = _best_stop_sequence(origin, trial_stops, lookup, config)
            if evaluation is None:
                continue

            endpoint = stops[-1]
            added_leg = _travel(lookup, endpoint, chunk["destination"])
            direct_leg = _travel(lookup, origin, chunk["destination"])
            if added_leg is None or direct_leg is None:
                continue

            marginal_distance_ratio = added_leg["distance_km"] / max(
                direct_leg["distance_km"], 1e-9
            )
            marginal_time_ratio = added_leg["travel_time_hours"] / max(
                direct_leg["travel_time_hours"], 1e-9
            )
            marginal_score = (
                config.distance_weight * marginal_distance_ratio
                + config.time_weight * marginal_time_ratio
                + config.economic_weight * evaluation["economic_ratio"]
            )

            candidates.append(
                (
                    0.5 * evaluation["detour_score"] + 0.5 * marginal_score,
                    evaluation["economic_ratio"],
                    evaluation["detour_score"],
                    marginal_distance_ratio,
                    marginal_time_ratio,
                    -quantity,
                    idx,
                )
            )

        if not candidates:
            break

        selected = min(candidates, key=lambda x: x[:5])
        idx = selected[6]
        selected_chunk = chunks.pop(idx)
        stops.append(selected_chunk["destination"])
        stop_loads.append(float(selected_chunk["quantity"]))

    evaluation = _best_stop_sequence(origin, stops, lookup, config)
    if evaluation is None:
        return None

    # Reorder the load amounts with the chosen stop permutation.
    load_by_destination: dict[str, float] = {}
    for destination, quantity in zip(stops, stop_loads):
        load_by_destination.setdefault(_hub_key(destination), 0.0)
        load_by_destination[_hub_key(destination)] += quantity
    ordered_loads = [load_by_destination[_hub_key(s)] for s in evaluation["sequence"]]
    parcels = sum(ordered_loads)

    total_weight = 0.0
    total_volume = 0.0
    for destination, qty in zip(evaluation["sequence"], ordered_loads):
        profile = parcel_profiles[_hub_key(destination)]
        total_weight += profile["avg_weight_kg"] * qty
        total_volume += profile["avg_volume_m3"] * qty

    # Schedule clock is a relative operating-hours approximation.
    route_hours = evaluation["travel_time_hours"] + config.driver_break_hours
    route_hours += config.staging_buffer_hours

    if config.return_to_origin:
        return_leg = _travel(lookup, evaluation["sequence"][-1], origin)
        if return_leg is None:
            return None
        route_hours += return_leg["travel_time_hours"]
        evaluation["distance_km"] += return_leg["distance_km"]
        evaluation["drive_time_hours"] += return_leg["travel_time_hours"]
        evaluation["travel_time_hours"] = route_hours
        evaluation["transport_cost"] += (
            config.cost_per_km * return_leg["distance_km"] * config.empty_return_factor
        )

    unload_hours = parcels * config.unloading_minutes_per_parcel / 60.0
    route_hours += unload_hours
    evaluation["travel_time_hours"] = route_hours

    if total_weight > config.max_weight_kg + 1e-9:
        return None
    if total_volume > config.max_volume_m3 + 1e-9:
        return None
    if route_hours > config.max_route_hours + 1e-9:
        return None

    capacity_utilization = parcels / float(config.parcel_capacity)
    return {
        "origin_hub": origin,
        "destination_hubs": evaluation["sequence"],
        "stop_parcels": ordered_loads,
        "parcels": parcels,
        "stops": len(evaluation["sequence"]),
        "weight_kg": total_weight,
        "volume_m3": total_volume,
        "distance_km": evaluation["distance_km"],
        "travel_time_hours": route_hours,
        "drive_time_hours": evaluation["drive_time_hours"],
        "baseline_distance_km": evaluation["baseline_distance_km"],
        "baseline_time_hours": evaluation["baseline_time_hours"],
        "distance_ratio": evaluation["distance_ratio"],
        "time_ratio": evaluation["time_ratio"],
        "distance_detour_pct": evaluation["distance_detour_pct"],
        "time_detour_pct": evaluation["time_detour_pct"],
        "detour_score": evaluation["detour_score"],
        "economic_ratio": evaluation["economic_ratio"],
        "direct_dispatch_cost": evaluation["direct_dispatch_cost"],
        "estimated_savings": evaluation["estimated_savings"],
        "estimated_savings_pct": evaluation["estimated_savings_pct"],
        "service_time_minutes_per_stop": config.service_time_minutes_per_stop,
        "transport_cost": evaluation["transport_cost"],
        "capacity_utilization": capacity_utilization,
        "weight_utilization": total_weight / max(config.max_weight_kg, 1e-9),
        "volume_utilization": total_volume / max(config.max_volume_m3, 1e-9),
        "vehicle_type": config.vehicle_type,
        "status": "planned",
    }


def _vehicle_candidates(fleet: pd.DataFrame | None, config: ConsolidatedRouteConfig):
    if fleet is None or fleet.empty:
        return [config]

    candidates = []
    for row in fleet.itertuples(index=False):
        if str(row.vehicle_type) == config.vehicle_type or config.vehicle_type == "any":
            candidates.append(
                ConsolidatedRouteConfig(
                    vehicle_type=str(row.vehicle_type),
                    parcel_capacity=int(row.parcel_capacity),
                    max_route_hours=min(
                        config.max_route_hours, float(row.max_trip_hours)
                    ),
                    fixed_trip_cost=float(row.fixed_trip_cost),
                    cost_per_km=float(row.cost_per_km),
                    max_stops=config.max_stops,
                    vehicle_count=int(row.vehicle_count),
                    operating_hours_per_day=float(row.operating_hours_per_day),
                    distance_weight=config.distance_weight,
                    time_weight=config.time_weight,
                    economic_weight=config.economic_weight,
                    service_time_minutes_per_stop=config.service_time_minutes_per_stop,
                    max_weight_kg=float(getattr(row, "max_weight_kg", 12000.0)),
                    max_volume_m3=float(getattr(row, "max_volume_m3", 65.0)),
                    loading_minutes=config.loading_minutes,
                    unloading_minutes_per_parcel=config.unloading_minutes_per_parcel,
                    driver_break_hours=config.driver_break_hours,
                    return_to_origin=config.return_to_origin,
                    empty_return_factor=config.empty_return_factor,
                    max_detour_pct=config.max_detour_pct,
                    max_time_detour_pct=config.max_time_detour_pct,
                    min_capacity_utilization=config.min_capacity_utilization,
                    origin_cutoff_hour=config.origin_cutoff_hour,
                    stop_cutoff_hour=config.stop_cutoff_hour,
                    staging_buffer_hours=config.staging_buffer_hours,
                )
            )
    return candidates or [config]


def build_consolidated_routes(
    demand: pd.DataFrame,
    hubs: pd.DataFrame,
    cost: pd.DataFrame,
    config: ConsolidatedRouteConfig | None = None,
    fleet: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Build a detour-aware, capacity-constrained linehaul plan.

    The upstream network optimizer decides OD flow. This layer turns that flow
    into physical multi-stop vehicle movements. Constraints include route time,
    stop count, weight, cube/volume, fleet hours, driver break allowance,
    optional return-to-origin, and a minimum practical load factor.

    This remains a deterministic heuristic, not a global VRP optimum.
    """
    config = config or ConsolidatedRouteConfig()

    if config.parcel_capacity <= 0 or config.max_stops <= 0:
        raise ValueError("Parcel capacity and stop limit must be positive")
    if config.max_route_hours <= 0 or config.vehicle_count <= 0:
        raise ValueError("Route hours and vehicle count must be positive")
    if config.operating_hours_per_day <= 0:
        raise ValueError("Operating hours must be positive")
    if config.service_time_minutes_per_stop < 0:
        raise ValueError("Service time cannot be negative")
    if config.min_capacity_utilization < 0 or config.min_capacity_utilization > 1:
        raise ValueError("Minimum utilization must be between 0 and 1")

    required = {"origin_hub", "destination_hub", "parcel_count"}
    missing = required - set(demand.columns)
    if missing:
        raise ValueError(f"Demand missing columns: {sorted(missing)}")

    d = demand.copy()
    d["parcel_count"] = pd.to_numeric(d["parcel_count"], errors="coerce").fillna(0).clip(lower=0)
    d = d.groupby(["origin_hub", "destination_hub"], as_index=False).parcel_count.sum()
    lookup = _route_lookup(cost)

    vehicle_configs = _vehicle_candidates(fleet, config)
    routes: list[dict] = []
    unmet: list[dict] = []
    direct_cost = 0.0
    total_requested = float(d["parcel_count"].sum())

    parcel_profiles: dict[str, dict[str, float]] = {}
    for row in d.itertuples(index=False):
        parcel_profiles[_hub_key(row.destination_hub)] = _parcel_profile(
            demand, row.origin_hub, row.destination_hub, float(row.parcel_count)
        )

    # Track fleet hours by vehicle type instead of one pooled hour bucket.
    fleet_hours_remaining = {
        candidate.vehicle_type: candidate.vehicle_count * candidate.operating_hours_per_day
        for candidate in vehicle_configs
    }

    for origin, group in d.groupby("origin_hub", sort=False):
        chunks: list[dict] = []

        for row in group.itertuples(index=False):
            destination = row.destination_hub
            quantity = float(row.parcel_count)
            if quantity <= 0:
                continue
            if _hub_key(origin) == _hub_key(destination):
                continue

            leg = _travel(lookup, origin, destination)
            if leg is None:
                unmet.append(
                    {
                        "origin_hub": origin,
                        "destination_hub": destination,
                        "unmet_parcels": quantity,
                        "reason": "missing_road_route",
                    }
                )
                continue

            if leg["travel_time_hours"] > config.max_route_hours:
                unmet.append(
                    {
                        "origin_hub": origin,
                        "destination_hub": destination,
                        "unmet_parcels": quantity,
                        "reason": "route_exceeds_max_hours",
                    }
                )
                continue

            best_direct_cost = min(
                math.ceil(quantity / max(candidate.parcel_capacity, 1))
                * (
                    candidate.fixed_trip_cost
                    + candidate.cost_per_km * leg["distance_km"]
                )
                for candidate in vehicle_configs
            )
            direct_cost += best_direct_cost

            for chunk_qty in _chunks(quantity, max(c.parcel_capacity for c in vehicle_configs)):
                chunks.append(
                    {
                        "destination": destination,
                        "quantity": min(float(chunk_qty), quantity),
                    }
                )
                quantity -= float(chunk_qty)
                if quantity <= 1e-9:
                    break

        while chunks:
            chunks.sort(key=lambda x: (-x["quantity"], str(x["destination"])))
            first = chunks.pop(0)

            candidate_routes = []
            for candidate in vehicle_configs:
                route = _build_route(
                    origin,
                    first,
                    list(chunks),
                    lookup,
                    candidate,
                    parcel_profiles,
                )
                if route is None:
                    continue
                if route["capacity_utilization"] < candidate.min_capacity_utilization and len(chunks) > 0:
                    continue

                hours_left = fleet_hours_remaining[candidate.vehicle_type]
                if route["travel_time_hours"] > hours_left + 1e-9:
                    continue

                candidate_routes.append(route)

            if not candidate_routes:
                unmet.append(
                    {
                        "origin_hub": origin,
                        "destination_hub": first["destination"],
                        "unmet_parcels": first["quantity"],
                        "reason": "no_feasible_vehicle_or_route",
                    }
                )
                continue

            chosen = min(
                candidate_routes,
                key=lambda r: (
                    r["transport_cost"] / max(r["parcels"], 1e-9),
                    r["detour_score"],
                    -r["capacity_utilization"],
                    r["travel_time_hours"],
                ),
            )
            routes.append(chosen)
            fleet_hours_remaining[chosen["vehicle_type"]] -= chosen["travel_time_hours"]

            # Remove the exact chunks used by the chosen route.
            used = {( _hub_key(d), float(q) ) for d, q in zip(chosen["destination_hubs"], chosen["stop_parcels"])}
            remaining_chunks = []
            used_once: set[tuple[str, float]] = set()
            for chunk in chunks:
                key = (_hub_key(chunk["destination"]), float(chunk["quantity"]))
                if key in used and key not in used_once:
                    used_once.add(key)
                    continue
                remaining_chunks.append(chunk)
            chunks = remaining_chunks

    route_rows = []
    for route_id, route in enumerate(routes, start=1):
        route_rows.append({"route_id": route_id, **route})

    out = pd.DataFrame(route_rows)
    unmet_df = pd.DataFrame(unmet)

    local_served = float(
        d.loc[
            d["origin_hub"].map(_hub_key).eq(d["destination_hub"].map(_hub_key)),
            "parcel_count",
        ].sum()
    )
    served = float(out["parcels"].sum()) if not out.empty else 0.0
    unmet_total = float(unmet_df["unmet_parcels"].sum()) if not unmet_df.empty else 0.0
    route_cost = float(out["transport_cost"].sum()) if not out.empty else 0.0

    metrics = {
        "status": "ok",
        "total_requested_parcels": total_requested,
        "served_parcels": served + local_served,
        "unmet_parcels": unmet_total,
        "service_level": (served + local_served) / max(total_requested, 1.0),
        "consolidated_routes": len(out),
        "average_stops": float(out["stops"].mean()) if not out.empty else 0.0,
        "average_capacity_utilization": float(out["capacity_utilization"].mean()) if not out.empty else 0.0,
        "average_weight_utilization": float(out["weight_utilization"].mean()) if not out.empty else 0.0,
        "average_volume_utilization": float(out["volume_utilization"].mean()) if not out.empty else 0.0,
        "total_transport_cost": route_cost,
        "direct_dispatch_cost": direct_cost,
        "estimated_cost_savings": direct_cost - route_cost,
        "estimated_cost_savings_pct": (
            100.0 * (direct_cost - route_cost) / direct_cost if direct_cost > 0 else 0.0
        ),
        "local_parcels_assumed_served": local_served,
        "fleet_hours_available": float(sum(
            candidate.vehicle_count * candidate.operating_hours_per_day
            for candidate in vehicle_configs
        )),
        "fleet_hours_used": float(
            sum(
                candidate.vehicle_count * candidate.operating_hours_per_day
                for candidate in vehicle_configs
            )
            - sum(fleet_hours_remaining.values())
        ),
        "fleet_hours_remaining": fleet_hours_remaining,
        "unmet_reasons": (
            unmet_df.groupby("reason")["unmet_parcels"].sum().to_dict()
            if not unmet_df.empty
            else {}
        ),
    }

    return out, metrics
