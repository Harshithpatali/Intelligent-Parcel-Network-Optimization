# Step 9 — Probabilistic Resilience Simulation

Step 9 replaces a small deterministic scenario grid with stochastic network stress testing.

## Random variables

- Demand multiplier: lognormal, clipped to 0.70–1.60
- Hub capacity multiplier: normal shock, clipped to 0.60–1.20
- Fleet availability multiplier: normal shock, clipped to 0.60–1.20
- Hub failure: independent 5% probability per hub per simulation
- Road-link failure: independent 2% probability per eligible OD link per simulation

Maximum simultaneous failures are capped at 2 hubs and 5 road links for interpretability.

These distributions are model assumptions for stress testing, not empirical estimates of a carrier's actual failure probabilities.

## Risk metrics

For each simulation:

- service level
- unmet demand
- transport cost
- objective including unmet-demand penalty
- number of failed hubs
- number of failed road links
- whether the service target was met

Across the simulation ensemble:

- probability of meeting the service target
- service-level P05/P50/P95
- unmet-demand P50/P95
- transport-cost P50/P95
- cost VaR at 95%
- cost CVaR at 95%

CVaR95 is the mean transport cost in the worst 5% cost tail.

## Reproducibility

The default random seed is 42 and is persisted with every simulation record. Changing the seed produces a different stochastic realization.

## Run

    python scripts/run_probabilistic_resilience.py

Run 1,000 simulations:

    python scripts/run_probabilistic_resilience.py --n-simulations 1000

Change service target:

    python scripts/run_probabilistic_resilience.py --service-target 0.98

Change failure assumptions:

    python scripts/run_probabilistic_resilience.py --hub-failure-probability 0.08 --route-failure-probability 0.04

Output:

    data/artifacts/probabilistic_resilience.csv

Supabase persistence:

- logistics_resilience_simulations
- logistics_resilience_risk_summary

## Interpretation

The output should be read as a model-based risk distribution, not as a forecast of actual carrier failures. The validity of the resulting probabilities depends on the assumed distributions and failure rates.

## Next extension

The next layer should estimate scenario probabilities from empirical historical logistics data where possible, introduce correlated regional disruptions, and run intervention optimization against the simulated risk distribution.