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
