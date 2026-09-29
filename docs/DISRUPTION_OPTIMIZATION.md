# Step 7 — Disruption-Aware Network Optimization

Step 7 turns the network optimizer into a scenario engine.

## Supported disruption classes

| Scenario | Model change |
|---|---|
| Baseline | No change |
| Demand surge | Multiply forecast OD demand |
| Capacity shock | Multiply hub capacity |
| Fleet shortage | Multiply available vehicle counts |
| Hub outage | Remove a hub and its incident routes |
| Road disruption | Remove a selected OD road connection |

Every scenario is solved with the same OR-Tools model, so results are directly comparable.

## Scenario metrics

Each run produces total requested parcels, served parcels, unmet demand, service level, transport cost, objective including unmet-demand penalty, incremental cost versus baseline, incremental unmet demand versus baseline, routing source, and forecast model version.

Flow-level outputs additionally retain vehicle type, trips, route distance, travel time, and transport cost.

## Important interpretation

The disruption definitions are planning scenarios, not historical claims about actual carrier events.

The standard benchmark scenarios are:

- 25% demand surge
- 25% hub-capacity reduction
- 30% fleet shortage
- one candidate-hub outage
- one candidate-road-link disruption

The hub and road selected by the deterministic benchmark helper are reproducible IDs from the current inferred network. They are not claimed to be real UPS facilities or real UPS routes.

## Run

First ensure Step 5 has generated forecast predictions:

    python scripts/train_hub_od_forecaster.py

Then:

    python scripts/run_disruption_scenarios.py

Optional date/model:

    python scripts/run_disruption_scenarios.py --forecast-date 2018-09-03 --model-version hub-od-xgb-v1

Results are written to data/artifacts/scenario_results.csv and, unless --no-persist is supplied, to logistics_scenario_results and logistics_scenario_flows.

## Decision-support interpretation

The model can answer questions such as:

- How much additional transport cost appears under a 25% demand surge?
- How much demand becomes unserved when hub capacity falls?
- How much service degradation occurs when fleet availability falls?
- What happens if a candidate hub is unavailable?
- Which OD connection becomes impossible when a road link is removed?

The next extension is a scenario frontier / resilience layer that searches combinations of demand, capacity, fleet, and network disruptions and identifies the minimum intervention required to maintain a chosen service-level constraint.