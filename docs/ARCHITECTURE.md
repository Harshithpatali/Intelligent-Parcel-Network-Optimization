# Architecture

Olist/Supabase -> ingestion -> data contracts -> feature engineering -> demand forecasting -> network optimization -> scenario simulation -> FastAPI -> Streamlit control tower.

The predictive layer estimates future parcel volume. The prescriptive layer converts demand into capacity-aware network decisions. Scenario analysis evaluates resilience under demand and capacity shocks.

The architecture intentionally separates prediction from optimization so each component can be validated independently and replaced without changing the API contract.
