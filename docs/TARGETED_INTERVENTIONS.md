# Step 10B — Targeted Resilience Intervention Optimization

This extension turns resilience planning into a targeted network design problem.

## Critical hub identification

Candidate hubs are ranked using outbound forecast demand, inbound forecast demand, total throughput exposure, and capacity pressure.

criticality = 0.5 * normalized throughput exposure + 0.5 * normalized capacity pressure

This is deliberately transparent rather than a black-box vulnerability score.

## Targeted interventions

For the top critical hubs, the engine generates:

- +10% hub-specific capacity
- +20% hub-specific capacity
- +30% hub-specific capacity
- 10% reserve-fleet allocation
- 20% reserve-fleet allocation
- backup capacity equivalent to 25%

Capacity uplift applies to the selected hub rather than silently increasing every hub.

## Route criticality

Routes are ranked using forecast route demand and route transport-cost exposure.

The current optimizer contains a single OD route matrix rather than an explicit road graph with alternate paths. Therefore route redundancy is not yet simulated as a real intervention. The system intentionally does not invent an alternate road.

A later road-graph extension can add alternate OSM paths, road-edge failure, k-shortest paths, route-specific redundancy, and detour capacity.

## Stochastic evaluation

Every candidate intervention is evaluated against identical Monte Carlo scenarios.

For intervention a:

P_target(a) = P(ServiceLevel(a) >= target)

Outputs include probability of meeting target, service P05/P50/P95, unmet demand P50/P95, transport-cost P50, transport-cost CVaR95, intervention cost, reliability improvement, service uplift, transport-cost delta, and Pareto efficiency.

## Run

Smoke test:

    python scripts/run_targeted_interventions.py --forecast-date YYYY-MM-DD --n-simulations 10 --no-persist

Full experiment:

    python scripts/run_targeted_interventions.py --forecast-date YYYY-MM-DD --model-version hub-od-xgb-v1 --n-simulations 500 --service-target 0.95 --top-hubs 5

Artifacts:

- data/artifacts/targeted_hub_ranking.csv
- data/artifacts/targeted_route_ranking.csv
- data/artifacts/targeted_interventions.csv

## Modeling boundary

The targeted cost assumptions and disruption distributions are synthetic stress-testing assumptions. They must not be presented as actual carrier costs or empirical failure probabilities.

The next research extension is intervention bundles: jointly select multiple hub capacity upgrades and reserve-fleet allocations under a finite budget, then optimize the bundle against the Monte Carlo scenarios.
