# Parcel Consolidation + Multi-Stop Routing

## Purpose

The network-flow optimizer decides how much forecast demand should move between hubs. This layer converts those OD flows into physical multi-stop linehaul routes so a truck can serve several destination hubs on one trip.

Example:

```
Hub 1 -> Hub 7: 12
       -> Hub 9: 15
       -> Hub 16: 10

37 parcels / 40 capacity = 92.5% utilization
```

## Method

The planner uses the existing Olist-calibrated 20-hub network, the real road-network distance/time matrix, and the production linehaul fleet availability.

For each origin hub:

1. Aggregate forecast OD demand.
2. Split any destination demand above vehicle capacity into capacity-sized chunks.
3. Start a route with the largest remaining demand chunk.
4. Add the nearest feasible destination chunk while respecting:
   - vehicle capacity
   - maximum route hours
   - maximum stops
5. Respect the available linehaul fleet-hour budget; excess demand becomes explicitly unmet.
6. Repeat until all feasible demand is assigned.
7. Compare consolidated route cost with direct OD dispatch cost.

The objective is operationally interpretable:

[
C_r = F + c_{km}D_r
]

where (F) is the fixed trip cost, (c_{km}) is the assumed cost per kilometre, and (D_r) is route distance.

Capacity utilization is:

[
U_r = \frac{Q_r}{Q_{vehicle}}
]

The implementation is a deterministic consolidation heuristic rather than a claim of globally optimal VRP solutions. It is intentionally separated from the existing network-flow optimizer so both decisions can be inspected.

## API

`POST /routing`

Default configuration:

- vehicle capacity: 40 parcels
- maximum route time: 16 hours
- maximum stops: 5
- linehaul fleet: read from `logistics_fleet` (`linehaul_truck`)
- fixed trip cost: 45
- cost per km: 0.075

The endpoint returns route sequences, parcel allocation by stop, distance, time, cost, utilization, service level, and modeled savings versus direct dispatches.

## Folium dashboard

The Streamlit **Routing** tab renders:

- candidate hub markers
- one colored line per consolidated route
- route tooltips/popups
- stop order
- parcel count
- capacity utilization
- route distance/time/cost
- modeled cost savings

The map lines connect hub coordinates. They are visualization connectors, not turn-by-turn road geometry; routing distances and travel times still come from the OSRM-backed road matrix.

## Limitations

This is a multi-stop linehaul consolidation layer, not a complete vehicle-routing system. It does not yet model:

- time windows
- parcel-level pickup/delivery sequencing
- loading/unloading service times
- driver shift regulations
- stochastic traffic
- exact road geometry for every displayed route
- cross-origin vehicle repositioning

Those can be added later without changing the upstream forecasting and resilience layers.
