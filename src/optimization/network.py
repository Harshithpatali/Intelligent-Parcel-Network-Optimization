import pandas as pd
try:
    from ortools.linear_solver import pywraplp
except ImportError:
    pywraplp = None

UNMET_PENALTY = 1000.0

def _hub_key(value):
    """Canonical key so string IDs (H01) and numeric IDs (1) remain usable."""
    if pd.isna(value):
        return "<NA>"
    return str(value).strip()



def build_cost_matrix(hubs):
    """Build a deterministic fallback cost matrix.

    Production routing should use the populated road matrix. For lightweight
    tests or hub catalogs that do not carry coordinates, use a neutral
    one-unit leg rather than crashing on a missing lat/lon column.
    """
    rows = []
    from src.core.geo import haversine_km
    has_coords = {"lat", "lon"}.issubset(hubs.columns)
    for _, a in hubs.iterrows():
        for _, b in hubs.iterrows():
            if _hub_key(a.hub_id) == _hub_key(b.hub_id):
                continue
            if has_coords and pd.notna(a.lat) and pd.notna(a.lon) and pd.notna(b.lat) and pd.notna(b.lon):
                km = haversine_km(float(a.lat), float(a.lon), float(b.lat), float(b.lon)) * 1.18
                travel_time = km / 60.0
            else:
                km = 1.0
                travel_time = 1.0
            rows.append({
                "origin_hub": a.hub_id,
                "destination_hub": b.hub_id,
                "distance_km": km,
                "unit_cost": 2.2 + 0.075 * km,
                "travel_time_hours": travel_time,
            })
    return pd.DataFrame(rows)


def build_road_cost_matrix(route_matrix):
    """Convert logistics_road_matrix rows into the optimizer cost schema."""
    r = route_matrix.copy()
    r = r[r.origin_hub_id != r.destination_hub_id].copy()
    r["origin_hub"] = r.origin_hub_id
    r["destination_hub"] = r.destination_hub_id
    r["distance_km"] = r.distance_km.astype(float)
    r["travel_time_hours"] = r.travel_time_hours.astype(float)
    r["unit_cost"] = 2.2 + 0.075 * r.distance_km
    return r[[
        "origin_hub", "destination_hub", "distance_km",
        "unit_cost", "travel_time_hours"
    ]]


def solve_network(demand, hubs, cost=None, capacity_multiplier=1.0,
                  service_level_target=0.95, fleet=None):
    """
    Optimize forecast parcel flows subject to hub capacity and synthetic fleet limits.

    fleet columns:
      vehicle_type, vehicle_count, parcel_capacity,
      operating_hours_per_day, fixed_trip_cost, cost_per_km, max_trip_hours
    """
    d = demand.copy()
    d["parcel_count"] = pd.to_numeric(d["parcel_count"]).clip(lower=0)
    d = d.groupby(["origin_hub", "destination_hub"], as_index=False)["parcel_count"].sum()
    cost = cost if cost is not None else build_cost_matrix(hubs)

    route = {}
    for _, r in cost.iterrows():
        route[(_hub_key(r.origin_hub), _hub_key(r.destination_hub))] = {
            "distance_km": float(r.distance_km),
            "travel_time_hours": float(r.travel_time_hours),
            "unit_cost": float(r.unit_cost),
        }

    caps = {
        _hub_key(row.hub_id): float(row.capacity_parcels) * capacity_multiplier
        for _, row in hubs.iterrows()
    }
    if fleet is None:
        fleet = pd.DataFrame([{
            "vehicle_type": "default",
            "vehicle_count": 10,
            "parcel_capacity": 20,
            "operating_hours_per_day": 12.0,
            "fixed_trip_cost": 25.0,
            "cost_per_km": 0.10,
            "max_trip_hours": 12.0,
        }])
    fleet = fleet.copy()

    if pywraplp is None:
        raise RuntimeError("OR-Tools is required for the fleet-constrained optimizer")

    # CBC is deterministic and available in standard OR-Tools distributions.
    # Fall back to SCIP when CBC is not packaged by the runtime.
    solver = pywraplp.Solver.CreateSolver("CBC_MIXED_INTEGER_PROGRAMMING")
    if not solver:
        solver = pywraplp.Solver.CreateSolver("SCIP")
    if not solver:
        raise RuntimeError("No supported OR-Tools mixed-integer solver is available")

    # Keep every demand route. If a route is absent because of a hub/road
    # disruption, its demand must remain in the denominator and become unmet.
    # Same-hub OD demand represents parcels whose origin and destination
    # fall in the same candidate hub catchment. It does not require a
    # linehaul route in this network model, so treat it as locally served
    # rather than incorrectly counting it as road/fleet unmet demand.
    local_parcels = float(
        d.loc[d["origin_hub"].map(_hub_key) == d["destination_hub"].map(_hub_key), "parcel_count"].sum()
    )
    routes = [
        ((r.origin_hub, r.destination_hub), float(r.parcel_count))
        for _, r in d.iterrows()
        if _hub_key(r.origin_hub) != _hub_key(r.destination_hub)
    ]
    if not routes and local_parcels <= 0:
        raise ValueError("Demand contains no OD routes")

    x = {}  # parcels by route and vehicle type
    y = {}  # integer trips by route and vehicle type
    u = {}  # unmet parcels by route

    for (o, j), q in routes:
        u[(o, j)] = solver.NumVar(0, solver.infinity(), f"unmet_{o}_{j}")
        route_vars = []
        route_key = (_hub_key(o), _hub_key(j))
        if route_key not in route:
            # No road arc exists: the entire OD demand is explicitly unmet.
            solver.Add(u[(o, j)] == q)
            continue
        for fi, fr in fleet.iterrows():
            vt = str(fr.vehicle_type)
            t = route[route_key]["travel_time_hours"]
            if t <= 0 or t > float(fr.max_trip_hours):
                continue
            max_trips_per_vehicle = max(
                1, int(float(fr.operating_hours_per_day) // t)
            )
            max_trips = int(fr.vehicle_count) * max_trips_per_vehicle
            y[(o, j, vt)] = solver.IntVar(0, max_trips, f"trips_{o}_{j}_{vt}")
            x[(o, j, vt)] = solver.NumVar(0, solver.infinity(), f"parcels_{o}_{j}_{vt}")
            solver.Add(
                x[(o, j, vt)] <= float(fr.parcel_capacity) * y[(o, j, vt)]
            )
            route_vars.append(x[(o, j, vt)])
        if not route_vars:
            solver.Add(u[(o, j)] == q)
        else:
            # Demand is conserved exactly: every parcel is either assigned to
            # a feasible vehicle trip or explicitly recorded as unmet.
            solver.Add(sum(route_vars) + u[(o, j)] == q)
            solver.Add(u[(o, j)] <= q)

    # Fleet hours are shared across the network: a vehicle cannot be counted on
    # multiple OD routes simultaneously.
    for _, fr in fleet.iterrows():
        vt = str(fr.vehicle_type)
        hour_terms = [
            float(route[(_hub_key(o), _hub_key(j))]["travel_time_hours"]) * y[(o, j, vt)]
            for (o, j), _ in routes
            if (o, j, vt) in y
        ]
        if hour_terms:
            solver.Add(sum(hour_terms) <= float(fr.vehicle_count) * float(fr.operating_hours_per_day))

    # Hub handling capacity applies to both outbound and inbound parcels.
    for h, cap in caps.items():
        outbound = [v for (o, j, vt), v in x.items() if _hub_key(o) == h]
        inbound = [v for (o, j, vt), v in x.items() if _hub_key(j) == h]
        if outbound:
            solver.Add(sum(outbound) <= cap)
        if inbound:
            solver.Add(sum(inbound) <= cap)

    obj = solver.Objective()
    for (o, j), _ in routes:
        u[(o, j)].SetBounds(0, solver.infinity())
        obj.SetCoefficient(u[(o, j)], UNMET_PENALTY)
        rc = route.get((_hub_key(o), _hub_key(j)))
        if rc is None:
            continue
        for _, fr in fleet.iterrows():
            vt = str(fr.vehicle_type)
            key = (o, j, vt)
            if key not in x:
                continue
            trip_cost = float(fr.fixed_trip_cost) + float(fr.cost_per_km) * rc["distance_km"]
            # Fixed-charge objective: dispatching a trip incurs its full
            # fixed + distance cost regardless of load. Charging x (parcels)
            # here would make lightly loaded trips appear artificially cheap.
            obj.SetCoefficient(y[key], trip_cost)
    obj.SetMinimization()

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        raise RuntimeError("Network optimization infeasible")

    rows = []
    for (o, j), requested in routes:
        route_unmet = u[(o, j)].solution_value()
        unmet_written = False
        for _, fr in fleet.iterrows():
            vt = str(fr.vehicle_type)
            key = (o, j, vt)
            if key not in x:
                continue
            parcels = x[key].solution_value()
            trips = int(round(y[key].solution_value()))
            if parcels == 0 and trips == 0:
                continue
            rc = route[(_hub_key(o), _hub_key(j))]
            trip_cost = float(fr.fixed_trip_cost) + float(fr.cost_per_km) * rc["distance_km"]
            rows.append({
                "origin_hub": o,
                "destination_hub": j,
                "vehicle_type": vt,
                "requested_parcels": requested,
                "parcels": parcels,
                "unmet_parcels": route_unmet if not unmet_written else 0.0,
                "trips": trips,
                "distance_km": rc["distance_km"],
                "travel_time_hours": rc["travel_time_hours"],
                "transport_cost": trips * trip_cost,
                "trip_cost": trip_cost,
                "capacity_utilization": parcels / max(float(fr.parcel_capacity) * max(trips, 1), 1.0),
                "status": "served",
            })
            unmet_written = True

        if not unmet_written and route_unmet > 0:
            rc = route.get((_hub_key(o), _hub_key(j)), {})
            rows.append({
                "origin_hub": o,
                "destination_hub": j,
                "vehicle_type": None,
                "requested_parcels": requested,
                "parcels": 0.0,
                "unmet_parcels": route_unmet,
                "trips": 0,
                "distance_km": rc.get("distance_km"),
                "travel_time_hours": rc.get("travel_time_hours"),
                "transport_cost": 0.0,
                "trip_cost": 0.0,
                "capacity_utilization": 0.0,
                "status": "unmet_no_feasible_vehicle",
            })

    out = pd.DataFrame(rows)
    total_requested = float(d.parcel_count.sum())
    total_unmet = float(sum(u[k].solution_value() for k in u))
    # The conservation equations are the authoritative source for service;
    # this remains correct even when a solver/runtime returns a numerically
    # sparse x-variable representation.
    total_served_network = max(
        float(d["parcel_count"].sum()) - local_parcels - total_unmet,
        0.0,
    )
    total_cost = float(out.transport_cost.sum()) if not out.empty else 0.0
    service = (local_parcels + total_served_network) / max(total_requested, 1.0)

    metrics = {
        "status": "optimal" if status == pywraplp.Solver.OPTIMAL else "feasible",
        "total_transport_cost": total_cost,
        "unmet_demand": total_unmet,
        "service_level": service,
        "service_level_target": service_level_target,
        "objective_with_unmet_penalty": total_cost + total_unmet * UNMET_PENALTY,
        "total_parcels": max(total_requested - total_unmet, 0.0),
        "network_served_parcels": total_served_network,
        "local_parcels_assumed_served": local_parcels,
        "fleet_vehicle_types": int(fleet.vehicle_type.nunique()),
        "routes_optimized": len(routes),
    }
    return out, metrics
