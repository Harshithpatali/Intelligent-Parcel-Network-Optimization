# Step 8 — Resilience Frontier

Step 8 searches a structured grid of demand, hub-capacity, and fleet-availability conditions instead of evaluating one disruption at a time.

## Default search space

- Demand multiplier: 1.00 to 1.50
- Capacity multiplier: 0.75 to 1.25
- Fleet multiplier: 0.70 to 1.30
- Service-level target: 95%

This produces 150 network scenarios with the default configuration.

## Optimization

Every point is passed through the same Step 7 scenario engine and OR-Tools network optimizer.

For each scenario the system records:

- service level
- unmet parcels
- transport cost
- objective including unmet-demand penalty
- whether the service-level target is achieved
- intervention score
- Pareto-frontier membership

## Pareto frontier

A scenario is Pareto-efficient when no other evaluated scenario simultaneously has lower or equal transport cost and higher or equal service level, with at least one strict improvement.

This provides a cost-versus-service trade-off view rather than selecting a single arbitrary operating point.

## Minimum-intervention search

Among scenarios meeting the service target, the runner identifies the candidate with the lowest normalized intervention score. This is a planning heuristic over the specified grid, not a globally optimal intervention unless the grid exhaustively represents the allowed decision space.

## Run

    python scripts/train_hub_od_forecaster.py
    python scripts/run_resilience_frontier.py

Custom service target:

    python scripts/run_resilience_frontier.py --service-target 0.98

Custom forecast date:

    python scripts/run_resilience_frontier.py --forecast-date 2018-09-03 --model-version hub-od-xgb-v1

Output:

    data/artifacts/resilience_frontier.csv

and, by default, the Supabase table `logistics_resilience_frontier`.

## Important modeling boundary

The frontier currently varies aggregate demand, capacity, and fleet availability. Hub outages and road-link failures remain available in Step 7 but are not yet part of the Cartesian frontier grid.

The next resilience extension should add probabilistic disruption sampling and joint hub/road outage combinations.