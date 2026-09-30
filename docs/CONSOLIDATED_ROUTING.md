# Parcel Consolidation + Multi-Stop Routing

## Purpose

The network-flow optimizer decides how much forecast demand should move between hubs. This layer converts those OD flows into physical multi-stop linehaul routes so one vehicle can serve several destinations when the consolidation is operationally defensible.

The model is intentionally split into two decisions:

1. **Network allocation:** forecast OD flow and capacity/fleet constraints.
2. **Physical routing:** vehicle selection, stop ordering, consolidation, and route feasibility.

This makes the decision chain auditable instead of hiding everything inside one heuristic.

## Operational constraints

The route planner can enforce:

- parcel-count capacity
- maximum route hours
- maximum number of stops
- weight capacity
- cubic-volume capacity
- loading time
- per-stop service time
- per-parcel unloading time
- driver-break allowance
- optional return-to-origin
- empty-return cost factor
- fleet-hour capacity by vehicle type
- minimum practical load factor
- maximum distance detour versus direct dispatch
- maximum travel-time detour versus direct dispatch

When parcel-level `weight_kg` and `volume_m3` fields are present, the planner estimates OD-specific average weight and cube. Otherwise it uses explicit planning defaults rather than pretending the data contain exact physical measurements.

## Detour-aware consolidation

For a route sequence R, the planner compares:

- route distance D_R
- direct-service distance D_0
- route operating time T_R
- direct-service time T_0
- consolidated transport cost C_R
- direct-dispatch cost C_0

Normalized detours are:

[
rho_D = D_R / D_0,qquad
rho_T = T_R / T_0
]

A candidate sequence is rejected when either detour exceeds the configured guardrail.

The candidate score combines:

- distance ratio
- time ratio
- economic ratio
- a marginal-leg check from the current endpoint

Thus the planner does not use a nearest-neighbour rule in isolation. For example, it can reject A -> B -> C when A -> C -> B is both shorter and faster.

For small stop sets, feasible permutations are evaluated directly. The default of five stops means at most 5! = 120 orderings for one candidate route.

## Direct-dispatch economics

For k independent destinations:

[
C_0 = kF + c_{km}D_0
]

For one consolidated route:

[
C_R = F + c_{km}D_R
]

where F is the fixed trip charge and c_km is the modeled distance charge.

The planner reports modeled savings:

[
S = C_0 - C_R
]

A positive S is only a modeled scenario result; it is not a claim about any real carrier's costs.

## Heterogeneous fleet

The API accepts `vehicle_type=any` or a specific fleet type. When a fleet table is available, the routing layer evaluates the eligible vehicle configurations and respects each type's:

- parcel capacity
- max trip hours
- fixed trip cost
- cost per kilometre
- vehicle count
- operating hours

Fleet hours are tracked separately by vehicle type, so a route does not consume capacity from an unrelated vehicle class.

## Unmet-demand accounting

Every OD quantity remains in the denominator. When a route cannot be built, the planner reports an explicit reason such as:

- `missing_road_route`
- `route_exceeds_max_hours`
- `no_feasible_vehicle_or_route`

This prevents infeasible demand from disappearing silently.

## Dashboard

The Streamlit **Routing** tab is the final operational map. It shows:

- hub markers
- one line per planned route
- stop order
- parcels per route and per stop
- parcel, weight and cube utilization
- distance and total operating time
- detour metrics
- modeled cost and savings
- unmet-demand reasons

The map is a visualization of hub-to-hub route connectors. When the OSRM matrix is populated, the optimizer's distance/time calculations use those road-network values.

## Known limitations

This is not a complete last-mile VRPTW solver. It still does not claim:

- turn-by-turn road geometry in the map
- live traffic
- exact driver legal rules for a specific jurisdiction
- parcel-level delivery time windows
- cross-origin tractor repositioning
- real carrier rates
- exact loading-bay appointment logic

Those require operational feeds and policy calibration.

## Production interpretation

Use the project as an open-data logistics research system:

- Olist provides observed historical order/parcel behaviour.
- OSM/OSRM provides open road-network routing when populated.
- Fleet, costs, service times and operating limits are scenario assumptions unless independently calibrated.

The system should therefore be presented as a mathematically constrained parcel-network optimization prototype, not as proprietary carrier software.
