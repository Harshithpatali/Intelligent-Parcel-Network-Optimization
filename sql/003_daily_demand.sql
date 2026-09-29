drop view if exists public.logistics_daily_demand;
create view public.logistics_daily_demand with (security_invoker=true) as
select purchase_date, seller_state origin_state, customer_state destination_state,
  count(*) parcel_count, count(distinct order_id) order_count,
  sum(coalesce(price,0)) item_value, sum(coalesce(freight_value,0)) freight_value,
  avg(seller_customer_distance_km) avg_distance_km,
  avg(product_weight_kg) avg_weight_kg, sum(coalesce(product_weight_kg,0)) total_weight_kg,
  sum(coalesce(product_volume_m3,0)) total_volume_m3
from public.logistics_fact_orders
group by purchase_date,seller_state,customer_state;
