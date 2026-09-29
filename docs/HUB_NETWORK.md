# Olist-Calibrated Geographic Hub Network

The project derives a candidate logistics network directly from observed Olist geography.

## Method

1. Aggregate parcel demand and seller activity by ZIP prefix.
2. Remove geocodes outside a conservative Brazil bounding envelope: latitude -34 to 6 and longitude -74 to -34.
3. Represent each ZIP as a point.
4. Transform points to geocentric EPSG:4978 and use the PostGIS point M coordinate as a positive demand/activity weight.
5. Generate 20 candidate hub clusters.
6. Place each candidate hub at the cluster centroid.
7. Keep the nearest observed ZIP as a representative location.
8. Assign fact rows with valid Brazilian coordinates to the nearest candidate origin/destination hub.
9. Aggregate assigned shipments into daily hub-to-hub demand.
10. Generate a geodesic hub-to-hub distance matrix.

PostGIS documents that POINT M coordinates can be used as weights in ST_ClusterKMeans and that geocentric clustering is suitable for geographic data.

## Current network

- Candidate hubs: 20
- Hub assignments: 112,077 item rows
- Distinct assigned orders: 98,159
- Hub-to-hub daily OD rows: 27,475
- Intra-hub assigned items: 31,092
- Candidate hub locations remain within the Brazil bounding envelope.

## Interpretation

These are candidate hubs inferred from Olist, not actual UPS, FedEx, DHL, or Olist facilities. Their purpose is to create a defensible logistics-network research environment from open data.

The project must not claim that these are historical Olist warehouses or real carrier facilities.

## Why demand-weighted clustering?

Uniform geographic clustering gives equal importance to sparse and dense regions. Demand-weighted clustering moves candidate hub locations toward areas where the observed dataset generates more logistics activity.

## Next layer

The hub network is ready for real road distance/time from OSRM or OpenStreetMap, demand forecasting per hub pair, synthetic but calibrated hub capacity, fleet generation, OR-Tools network-flow optimization, disruption scenarios, and service-level/cost comparisons.
