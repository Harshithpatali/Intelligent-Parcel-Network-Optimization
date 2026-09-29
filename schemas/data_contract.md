# Data Contracts

## Demand
Required columns: timestamp, origin_hub, destination_hub, parcel_count. Parcel count must be numeric and non-negative. Timestamp must be parseable as a datetime.

## Parcels
Required columns: parcel_id, origin_hub, destination_hub, weight_kg, volume_m3, deadline. IDs must be unique and physical quantities must be non-negative.

## Hubs
Required columns: hub_id, lat, lon, capacity_parcels. Hub IDs must be unique and coordinates valid.

## Contract principle
Validation runs before model training and optimization. Invalid data fails fast rather than silently entering the decision layer.
