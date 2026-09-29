# Data Sources and Provenance

## Core data
The project is designed around Olist tables in the user's Supabase ecommerce-intelligence project. Verified source: 99,441 orders spanning 2016-09-04 through 2018-10-17, customers, items, products, sellers and about one million geolocation rows.

## External enrichment
- IBGE Localidades API for municipality identifiers and geography.
- OpenStreetMap / Geofabrik PBF extracts for road-network enrichment.
- OSRM for optional route distance/time calculations.
- INMET BDMEP for historical weather observations.
- Brazilian holiday data for SLA/calendar features.

## Modeling boundary
No external source is represented as UPS proprietary data. Hub capacity, fleet and vehicle availability are synthetic operational parameters calibrated from open-data demand.
