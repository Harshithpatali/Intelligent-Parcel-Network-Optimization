# Logistics Fact Table

## Grain
One row per Olist order item (`order_id + order_item_id`). This grain preserves parcel-level commercial and physical attributes while retaining order-level lifecycle timestamps.

## Dimensions joined
- order lifecycle/status
- customer geography
- seller geography
- product category and physical dimensions
- ZIP-prefix geolocation

## Derived operational features
- purchase date/hour/day/month
- actual delivery duration
- delivery delay versus estimate
- seller-to-customer geodesic distance
- weight in kg
- volume in m³
- geolocation availability flag

## Current Supabase validation
The live build produced 112,650 fact rows, 98,666 distinct orders, 98,666 customers and 3,095 sellers. 112,096 rows contain both customer and seller coordinates (99.51%). Average seller-customer geodesic distance is 594.60 km. Item value is 13,591,643.70 and freight value is 2,251,909.54 in the dataset's monetary units.

## Important modeling choice
The fact table is item-grain rather than order-grain because an order may contain multiple products/sellers. For demand forecasting, aggregate this table to the required time/network grain rather than treating every item as an independent customer shipment.
