# Step 10C — Intervention Bundle Optimization

Step 10A compared broad interventions. Step 10B identified targeted hubs. Step 10C selects combinations of targeted interventions under an explicit budget and reliability constraint.

## Mathematical problem

Let z define a selected intervention bundle.

Minimize:

J(z) = C(z) + lambda_u E[UnmetDemand(z)] + lambda_c CVaR95(TransportCost(z))

subject to:

P(ServiceLevel(z) >= tau) >= R*

C(z) <= B

where B is the intervention budget, tau is the service target, R* is required reliability, and the lambda terms weight residual risk.

## Candidate generation

Candidates come from the most critical hubs identified in Step 10B:

- +10% hub capacity
- +20% hub capacity
- +30% hub capacity
- +25% backup capacity

The runner enumerates combinations up to `--max-bundle-size`, while discarding bundles above the budget before Monte Carlo evaluation.

## Stochastic design

Every candidate bundle is evaluated against the same Monte Carlo scenario set. This paired design reduces comparison noise.

## Outputs

- intervention cost
- probability of meeting service target
- service P05/P50
- unmet-demand P95
- expected unmet demand
- transport cost P50
- transport cost CVaR95
- objective value
- feasibility
- selected interventions
- Pareto efficiency

## Run

Smoke test:

    python scripts/run_intervention_bundles.py --forecast-date YYYY-MM-DD --n-simulations 10 --budget 100 --max-bundle-size 2 --no-persist

Full experiment:

    python scripts/run_intervention_bundles.py --forecast-date YYYY-MM-DD --model-version hub-od-xgb-v1 --n-simulations 500 --budget 100 --required-reliability 0.90 --service-target 0.95 --max-bundle-size 3

Artifact:

    data/artifacts/intervention_bundles.csv

## Computational boundary

If there are N candidate interventions, exhaustive enumeration through bundle size K requires sum(C(N,k), k=0..K) bundles. The bounded bundle size is intentional. As the candidate set grows, the next version should screen candidates using marginal risk reduction and then solve the reduced bundle problem with MILP or stochastic programming.

## Modeling boundary

Intervention costs and disruption distributions remain synthetic stress-test assumptions until calibrated with empirical operational data. The optimizer demonstrates the methodology and engineering architecture, not proprietary carrier investment economics.
