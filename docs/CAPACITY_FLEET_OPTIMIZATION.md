# Step 6 — Capacity, Fleet, and Network Optimization

## What this step adds

The network now has three planning layers:

1. Hub capacity calibration from observed Olist throughput.
2. Synthetic fleet scenario with vehicle capacity, operating hours, route-time limits, and cost assumptions.
3. Forecast-driven OR-Tools optimization that allocates predicted OD parcels subject to hub and fleet constraints.

## Hub capacity

For each candidate hub:

- Calculate daily outbound parcels.
- Calculate daily inbound parcels.
- Estimate the 95th percentile of each series.
- Set capacity to max(10, ceil(max(P95 outbound, P95 inbound) × 1.25)).

The 1.25 factor is a scenario safety buffer. It is not a claim about a real carrier's engineering standard.

Current Supabase result:

- 20 candidate hubs
- minimum capacity: 10 parcels/day
- maximum capacity: 240 parcels/day
- average capacity: 34.4 parcels/day
- total nominal hub capacity: 688 parcels/day

## Synthetic fleet

| Vehicle | Count | Parcels/trip | Operating hours | Max trip | Fixed trip cost | Cost/km |
|---|---:|---:|---:|---:|---:|---:|
| linehaul_truck | 10 | 40 | 16 h | 16 h | 45 | 0.075 |
| medium_truck | 14 | 20 | 14 h | 12 h | 25 | 0.090 |
| delivery_van | 20 | 8 | 12 h | 8 h | 12 | 0.120 |

All fleet values are synthetic scenario assumptions.

## Optimization model

For route (origin, destination) and vehicle type v:

- x[o,j,v] = parcels assigned to vehicle type v
- y[o,j,v] = integer trips
- u[o,j] = unmet parcels

Capacity constraint:

x[o,j,v] <= parcel_capacity[v] * y[o,j,v]

Demand constraint:

sum_v x[o,j,v] + u[o,j] >= forecast[o,j]

Hub capacity:

sum_j,v x[o,j,v] <= origin_capacity
sum_i,v x[i,o,v] <= destination_capacity

Fleet availability is shared across the entire network:

sum_route travel_time[route] * y[route,v] <= vehicle_count[v] * operating_hours[v]

A route is only eligible for a vehicle when its travel time is within that vehicle's maximum trip duration.

The objective minimizes transport cost plus a large unmet-demand penalty. This makes service protection explicit rather than silently dropping forecast demand.

## Running Step 6

First train the Step 5 forecast model:

    python scripts/train_hub_od_forecaster.py

Then run the optimizer:

    python scripts/run_forecast_optimization.py

Optional:

    python scripts/run_forecast_optimization.py --forecast-date 2018-09-03
    python scripts/run_forecast_optimization.py --forecast-date 2018-09-03 --model-version hub-od-xgb-v1
    python scripts/run_forecast_optimization.py --capacity-multiplier 1.10

The runner:

1. Loads the selected XGBoost forecast from logistics_forecast_predictions.
2. Loads calibrated hub capacities.
3. Loads the synthetic fleet.
4. Uses OSRM road routing if logistics_road_matrix has been populated.
5. Otherwise uses the explicitly labeled analytical Haversine fallback.
6. Solves the fleet-constrained OR-Tools model.
7. Writes data/artifacts/optimized_forecast_flows.csv.

## Important current state

The OSRM matrix currently contains zero rows because the execution environment could not reach the external routing service. The optimizer therefore uses the analytical fallback until scripts/build_osrm_matrix.py is run from a machine or CI environment with outbound HTTPS access.

The XGBoost forecasting pipeline has also been implemented but has not yet been executed in this environment. Therefore no XGBoost accuracy numbers are claimed here.

## Production interpretation

This is an Olist-calibrated network planning model, not a reconstruction of a proprietary UPS network. The defensible claims are:

- real historical parcel transactions,
- real observed seller/customer geography,
- inferred candidate hubs,
- open road-network routing when available,
- forecasted OD demand,
- statistically calibrated hub capacities,
- explicit fleet assumptions,
- constrained mathematical optimization.

The next layer is scenario optimization: disruption-aware routing, hub outages, capacity shocks, demand surges, and service-level trade-offs.
