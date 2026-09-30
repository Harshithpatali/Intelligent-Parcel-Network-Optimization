from __future__ import annotations

from dataclasses import dataclass
import math
import itertools
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


def _route_lookup(cost: pd.DataFrame) -> dict[tuple[object, object], dict[str, float]]:
    required = {
        "origin_hub",
        "destination_hub",
        "distance_km",
        "travel_time_hours",
    }
    missing = required - set(cost.columns)
    if missing:
        raise ValueError(f"Cost matrix missing columns: {sorted(missing)}")

    lookup: dict[tuple[object, object], dict[str, float]] = {}
    for row in cost.itertuples(index=False):
        lookup[(row.origin_hub, row.destination_hub)] = {
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
    return lookup.get((origin, destination))



def _route_metrics(origin, stops, lookup):
    distance = 0.0
    hours = 0.0
    current = origin
    for destination in stops:
        leg = _travel(lookup, current, destination)
        if leg is None:
            return None
        distance += leg["distance_km"]
        hours += leg["travel_time_hours"]
        current = destination
    return distance, hours


def _improve_stop_order(origin, stops, lookup):
    """
    Improve the stop sequence using pairwise 2-opt-style reversals.

    A candidate sequence is accepted only when it is no worse on both
    distance and travel time and strictly better on at least one. This
    prevents a route such as A->B->C from surviving when A->C->B is
    simultaneously shorter and faster.
    """
    sequence = list(stops)
    current = _route_metrics(origin, sequence, lookup)
    if current is None or len(sequence) < 2:
        return sequence, current

    changed = True
    while changed:
        changed = False
        best_sequence = sequence
        best_metrics = current

        for i in range(len(sequence) - 1):
            for j in range(i + 1, len(sequence)):
                candidate = sequence[:i] + list(reversed(sequence[i:j + 1])) + sequence[j + 1:]
                metrics = _route_metrics(origin, candidate, lookup)
                if metrics is None:
                    continue
                d, t = metrics
                bd, bt = best_metrics
                if d <= bd + 1e-9 and t <= bt + 1e-9 and (d < bd - 1e-9 or t < bt - 1e-9):
                    best_sequence = candidate
                    best_metrics = metrics

        if best_sequence != sequence:
            sequence = best_sequence
            current = best_metrics
            changed = True

    return sequence, current

def _sequence_metrics(origin, sequence, lookup):
    distance = 0.0
    hours = 0.0
    current = origin
    for destination in sequence:
        leg = _travel(lookup, current, destination)
        if leg is None:
            return None
        distance += leg["distance_km"]
        hours += leg["travel_time_hours"]
        current = destination
    return distance, hours


def _best_stop_sequence(origin, stops, lookup, max_route_hours):
    """
    Evaluate feasible permutations of a small stop set.

    For two stops A->B->C versus A->C->B, the planner explicitly checks
    both distance and time. A route is not accepted merely because it
    carries more parcels: a dominated sequence (higher distance AND higher
    travel time) is rejected in favour of the non-dominated ordering.
    """
    best = None
    for sequence in itertools.permutations(stops):
        metrics = _sequence_metrics(origin, sequence, lookup)
        if metrics is None:
            continue
        distance, hours = metrics
        if hours > max_route_hours + 1e-9:
            continue
        candidate = (distance, hours, tuple(str(x) for x in sequence), sequence)
        if best is None or candidate[:3] < best[:3]:
            best = candidate
    return None if best is None else {
        "sequence": list(best[3]),
        "distance_km": best[0],
        "travel_time_hours": best[1],
    }


def _build_route(
    origin,
    first_stop,
    first_load,
    chunks,
    lookup,
    config: ConsolidatedRouteConfig,
):
    stops = [first_stop]
    load_by_stop = {first_stop: first_load}

    while len(stops) < config.max_stops:
        candidates = []
        for idx, (destination, quantity) in enumerate(chunks):
            if quantity + sum(load_by_stop.values()) > config.parcel_capacity + 1e-9:
                continue
            trial_stops = stops + [destination]
            metrics = _best_stop_sequence(
                origin, trial_stops, lookup, config.max_route_hours
            )
            if metrics is None:
                continue
            candidates.append(
                (
                    metrics["distance_km"],
                    metrics["travel_time_hours"],
                    -quantity,
                    idx,
                    destination,
                    quantity,
                )
            )

        if not candidates:
            break

        _, _, _, idx, destination, quantity = min(candidates)
        chunks.pop(idx)
        stops.append(destination)
        load_by_stop[destination] = quantity

    sequence_result = _best_stop_sequence(
        origin, stops, lookup, config.max_route_hours
    )
    if sequence_result is None:
        return None

    sequence = sequence_result["sequence"]
    loads = [load_by_stop[s] for s in sequence]
    load = sum(loads)

    return {
        "origin_hub": origin,
        "destination_hubs": sequence,
        "stop_parcels": loads,
        "parcels": load,
        "stops": len(sequence),
        "distance_km": sequence_result["distance_km"],
        "travel_time_hours": sequence_result["travel_time_hours"],
        "transport_cost": config.fixed_trip_cost + config.cost_per_km * sequence_result["distance_km"],
        "capacity_utilization": load / float(config.parcel_capacity),
        "vehicle_type": config.vehicle_type,
    }


def build_consolidated_routes(
    demand: pd.DataFrame,
    hubs: pd.DataFrame,
    cost: pd.DataFrame,
    config: ConsolidatedRouteConfig | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Build capacitated multi-stop linehaul routes from forecast hub-to-hub demand.

    The planner keeps the existing Olist hub network and real road-network
    distance/time matrix. For each origin hub it repeatedly starts a route with
    the largest remaining destination chunk, then adds the nearest feasible
    destination chunks while respecting vehicle capacity, route time, and
    stop limits.

    This is a deterministic consolidation heuristic, not a claim of global
    VRP optimality. It is intentionally separate from the existing network-flow
    optimizer so the portfolio can compare direct OD dispatches with physical
    multi-stop routes.
    """
    config = config or ConsolidatedRouteConfig()
    if config.parcel_capacity <= 0 or config.max_stops <= 0 or config.max_route_hours <= 0:
        raise ValueError("Route capacity, stop limit, and route hours must be positive")
    if config.vehicle_count <= 0 or config.operating_hours_per_day <= 0:
        raise ValueError("Vehicle count and operating hours must be positive")

    required = {"origin_hub", "destination_hub", "parcel_count"}
    missing = required - set(demand.columns)
    if missing:
        raise ValueError(f"Demand missing columns: {sorted(missing)}")

    d = demand.copy()
    d["parcel_count"] = pd.to_numeric(d["parcel_count"], errors="coerce").fillna(0).clip(lower=0)
    d = (
        d.groupby(["origin_hub", "destination_hub"], as_index=False)["parcel_count"]
        .sum()
    )
    lookup = _route_lookup(cost)

    routes = []
    unmet = []
    direct_cost = 0.0
    total_requested = float(d["parcel_count"].sum())

    remaining_fleet_hours = float(config.vehicle_count) * float(config.operating_hours_per_day)

    for origin, group in d.groupby("origin_hub", sort=False):
        chunks = []
        for row in group.itertuples(index=False):
            destination = row.destination_hub
            quantity = float(row.parcel_count)
            if quantity <= 0:
                continue
            if origin == destination:
                # Same-hub demand is local handling, not a linehaul trip.
                continue
            if (origin, destination) not in lookup:
                unmet.append(
                    {
                        "origin_hub": origin,
                        "destination_hub": destination,
                        "unmet_parcels": quantity,
                        "reason": "missing_road_route",
                    }
                )
                continue

            leg = lookup[(origin, destination)]
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

            direct_trips = math.ceil(quantity / config.parcel_capacity)
            direct_cost += direct_trips * (
                config.fixed_trip_cost + config.cost_per_km * leg["distance_km"]
            )
            for chunk in _chunks(quantity, config.parcel_capacity):
                chunks.append((destination, chunk))

        while chunks:
            # Largest demand first creates useful consolidation anchors.
            chunks.sort(key=lambda x: (-x[1], str(x[0])))
            first_destination, first_quantity = chunks.pop(0)
            route = _build_route(
                origin,
                first_destination,
                first_quantity,
                chunks,
                lookup,
                config,
            )
            if route is None:
                unmet.append(
                    {
                        "origin_hub": origin,
                        "destination_hub": first_destination,
                        "unmet_parcels": first_quantity,
                        "reason": "no_feasible_road_leg",
                    }
                )
                continue
            if route["travel_time_hours"] > remaining_fleet_hours + 1e-9:
                unmet.append({
                    "origin_hub": origin,
                    "destination_hub": first_destination,
                    "unmet_parcels": route["parcels"],
                    "reason": "fleet_hours_exhausted",
                })
                continue
            remaining_fleet_hours -= route["travel_time_hours"]
            routes.append(route)

    route_rows = []
    for route_id, route in enumerate(routes, start=1):
        route_rows.append(
            {
                "route_id": route_id,
                "origin_hub": route["origin_hub"],
                "destination_hubs": route["destination_hubs"],
                "stop_parcels": route["stop_parcels"],
                "parcels": route["parcels"],
                "stops": route["stops"],
                "distance_km": route["distance_km"],
                "travel_time_hours": route["travel_time_hours"],
                "transport_cost": route["transport_cost"],
                "capacity_utilization": route["capacity_utilization"],
                "vehicle_type": route["vehicle_type"],
                "status": "consolidated_route",
            }
        )

    out = pd.DataFrame(route_rows)
    unmet_df = pd.DataFrame(unmet)

    local_served = float(
        d.loc[d["origin_hub"] == d["destination_hub"], "parcel_count"].sum()
    )
    served = float(out["parcels"].sum()) if not out.empty else 0.0
    unmet_total = float(unmet_df["unmet_parcels"].sum()) if not unmet_df.empty else 0.0
    route_cost = float(out["transport_cost"].sum()) if not out.empty else 0.0
    route_count = len(out)
    avg_utilization = (
        float(out["capacity_utilization"].mean()) if not out.empty else 0.0
    )

    metrics = {
        "status": "ok",
        "total_requested_parcels": total_requested,
        "served_parcels": served + local_served,
        "unmet_parcels": unmet_total,
        "service_level": (served + local_served) / max(total_requested, 1.0),
        "consolidated_routes": route_count,
        "average_stops": float(out["stops"].mean()) if not out.empty else 0.0,
        "average_capacity_utilization": avg_utilization,
        "total_transport_cost": route_cost,
        "direct_dispatch_cost": direct_cost,
        "estimated_cost_savings": direct_cost - route_cost,
        "estimated_cost_savings_pct": (
            100.0 * (direct_cost - route_cost) / direct_cost
            if direct_cost > 0
            else 0.0
        ),
        "local_parcels_assumed_served": local_served,
        "fleet_hours_available": float(config.vehicle_count * config.operating_hours_per_day),
        "fleet_hours_used": float(config.vehicle_count * config.operating_hours_per_day - remaining_fleet_hours),
        "fleet_hours_remaining": float(remaining_fleet_hours),
    }

    if not unmet_df.empty:
        metrics["unmet_reasons"] = unmet_df.groupby("reason")["unmet_parcels"].sum().to_dict()
    else:
        metrics["unmet_reasons"] = {}

    return out, metrics
