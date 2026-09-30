# Intelligent Parcel Network Optimization

Industry-oriented predictive + prescriptive logistics platform built around the public Olist Brazilian e-commerce dataset and open geospatial/weather enrichment.

> Open-data research prototype inspired by parcel-network operations. It does not represent UPS proprietary data, systems, costs, hubs, or operational rules.

## Architecture
- Olist/Supabase + IBGE + OSM/OSRM + INMET + holiday data
- Data validation and contracts
- Leakage-safe time-series forecasting
- OR-Tools network allocation with unmet-demand penalty
- Demand surge, hub outage and combined disruption scenarios
- FastAPI typed API with health/readiness and request IDs
- Prometheus metrics and structured logging
- Streamlit control tower
- Docker, Compose, CI and Kubernetes templates

## Quick start
```bash
cp .env.example .env
python -m venv .venv
pip install -r requirements.txt
python scripts/generate_demo.py
python scripts/validate_data.py
pytest -q
uvicorn src.api.main:app --reload --port 8000
```

Dashboard: `streamlit run app/streamlit_app.py`

Docker: `docker compose up --build`

## API
GET /health, /ready, /metrics, /network
POST /forecast, /optimize, /scenario

Protected endpoints require X-API-Key when API_KEY is configured.

## Optimization
For each origin-destination pair, x_ij is transported volume and u_ij is unmet volume. The objective minimizes transport cost plus a large unmet-demand penalty subject to network capacity and demand constraints. Service level is 1 - unmet_demand / total_demand.

## Data boundary
Olist does not contain a real carrier hub/fleet network. The project therefore constructs a synthetic network calibrated from observed Olist geography and parcel behavior. It must not be presented as proprietary UPS data.

## Production roadmap
Complete RBAC/SSO, private networking, secrets management, real routing data, asynchronous optimization jobs, audit persistence, drift monitoring, load testing, disaster recovery, and stakeholder-calibrated cost/capacity constraints before live operational use.


## Pre-deployment gate

Before deploying the research application, populate the real road matrix and forecast predictions, then run:

```bash
python scripts/pre_deploy_check.py
```

Optional date-specific validation:

```bash
FORECAST_DATE=2018-09-03 MODEL_VERSION=hub-od-xgb-v1 python scripts/pre_deploy_check.py
```

The gate verifies candidate hubs, road-network pairs, forecast predictions, calibrated hub capacity, and fleet configuration. It intentionally blocks deployment when those production artifacts are missing.

## Resilience decision layer

The project now extends beyond deterministic network allocation:

1. disruption-aware optimization
2. deterministic resilience frontier
3. probabilistic Monte Carlo resilience
4. broad intervention optimization
5. targeted hub intervention optimization
6. budget-constrained intervention bundles

Intervention costs and disruption distributions are explicitly synthetic stress-test assumptions unless calibrated with operational data.

## Deployment boundary

The FastAPI + Streamlit container is deployment-ready as a research application. The deployed API uses demo data unless the production data-serving layer is explicitly wired to the populated Supabase artifacts. Do not represent demo outputs as live carrier operations.

For the final deployment, run the pre-deployment gate, populate the OSRM matrix from an outbound-HTTPS runner, execute the forecast training pipeline, validate the resulting metrics, and then deploy the container.


## Physical routing upgrade

The routing layer now models a broader set of parcel-linehaul constraints:

- heterogeneous vehicle selection from the fleet table
- parcel-count, weight and cube/volume capacity
- explicit loading, unloading and driver-break time
- optional return-to-origin and empty-return economics
- maximum distance and time detour guardrails versus direct dispatch
- fleet-hour capacity tracked by vehicle type
- minimum practical load-factor rule
- parcel-level weight/volume profiles when available in the input data
- explicit unmet-demand reason codes

The route planner remains a deterministic, auditable heuristic rather than a claim of global VRP optimality. The upstream network-flow optimizer continues to decide OD allocation; this routing layer converts that allocation into physical trips.

## Real-world data boundary

Open Olist transactions and open geospatial/routing data are inputs to the research system. Carrier-specific costs, driver rules, handling SLAs, fleet composition, and other operational policies are scenario assumptions unless explicitly calibrated from an external source. The application therefore reports modeled outcomes rather than representing any carrier's proprietary operating network.
