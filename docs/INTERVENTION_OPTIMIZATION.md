# Step 10 — Resilience Intervention Optimization

Step 9 measures stochastic network risk. Step 10 evaluates what operational intervention changes that risk and compares modeled intervention cost with reliability improvement.

## Decision model

For intervention a and stochastic scenario s:

R(a) = P(service_level(a,s) >= service_target)

Intervention cost:

C(a) = fixed_cost + horizon_days * variable_cost

A constrained planning formulation is:

minimize C(a), subject to R(a) >= required_reliability

The richer risk view reports service-level quantiles, unmet-demand tail risk and transport-cost CVaR95.

## Common-random-number design

Every intervention is evaluated against the same sampled demand, capacity and disruption scenarios. This paired design reduces Monte Carlo noise when comparing interventions.

## Initial intervention catalog

- +10% network-wide hub capacity
- +20% network-wide hub capacity
- +10% operating fleet
- +20% operating fleet
- +10% reserve fleet

The cost coefficients are explicit portfolio assumptions for the project. They are not proprietary carrier economics.

## Outputs

- probability of meeting service target
- service P05/P50/P95
- unmet demand P50/P95
- transport cost P50
- transport cost CVaR95
- intervention cost
- reliability improvement
- median service uplift
- median transport-cost delta
- feasibility against the requested service target
- Pareto efficiency

## Run

The Step 5 forecast must exist for the requested forecast date.

Smoke test:

    python scripts/run_intervention_optimization.py --forecast-date YYYY-MM-DD --n-simulations 10 --no-persist

Full run:

    python scripts/run_intervention_optimization.py --forecast-date YYYY-MM-DD --model-version hub-od-xgb-v1 --n-simulations 500 --service-target 0.95

Results are written to data/artifacts/intervention_optimization.csv and, unless --no-persist is supplied, to the Step 10 Supabase tables.

## Modeling boundary

No Step 10 performance number should be reported until Step 5 forecasting and the route matrix have been populated and the runner has actually executed.

The next extension is targeted intervention optimization: backup capacity at specific hubs, route redundancy, reserve vehicles allocated by region, and intervention bundles.