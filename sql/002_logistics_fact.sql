create extension if not exists postgis;

drop table if exists public.logistics_fact_orders;
create table public.logistics_fact_orders as
with geo as (
  select distinct on (geolocation_zip_code_prefix) geolocation_zip_code_prefix, geolocation_lat, geolocation_lng
  from public.olist_geolocation
  where geolocation_lat is not null and geolocation_lng is not null
  order by geolocation_zip_code_prefix, geolocation_lat, geolocation_lng
), base as (
  select i.order_id,i.order_item_id,i.product_id,i.seller_id,o.customer_id,o.order_status,
    o.order_purchase_timestamp,o.order_approved_at,o.order_delivered_carrier_date,o.order_delivered_customer_date,o.order_estimated_delivery_date,
    i.shipping_limit_date,i.price,i.freight_value,p.product_category_name,p.product_weight_g,p.product_length_cm,p.product_height_cm,p.product_width_cm,
    c.customer_zip_code_prefix,c.customer_city,c.customer_state,s.seller_zip_code_prefix,s.seller_city,s.seller_state,
    cg.geolocation_lat customer_lat,cg.geolocation_lng customer_lng,sg.geolocation_lat seller_lat,sg.geolocation_lng seller_lng
  from public.olist_order_items i
  join public.olist_orders o on o.order_id=i.order_id
  join public.olist_customers c on c.customer_id=o.customer_id
  join public.olist_sellers s on s.seller_id=i.seller_id
  left join public.olist_products p on p.product_id=i.product_id
  left join geo cg on cg.geolocation_zip_code_prefix=c.customer_zip_code_prefix
  left join geo sg on sg.geolocation_zip_code_prefix=s.seller_zip_code_prefix
)
select *, order_purchase_timestamp::date purchase_date, extract(hour from order_purchase_timestamp)::int purchase_hour,
  extract(dow from order_purchase_timestamp)::int purchase_dow, extract(month from order_purchase_timestamp)::int purchase_month,
  case when order_delivered_customer_date is not null and order_estimated_delivery_date is not null then extract(epoch from (order_delivered_customer_date-order_estimated_delivery_date))/86400.0 end delivery_delay_days,
  case when order_delivered_customer_date is not null then extract(epoch from (order_delivered_customer_date-order_purchase_timestamp))/86400.0 end actual_delivery_days,
  case when customer_lat is not null and seller_lat is not null then st_distance(st_setsrid(st_makepoint(customer_lng,customer_lat),4326)::geography,st_setsrid(st_makepoint(seller_lng,seller_lat),4326)::geography)/1000.0 end seller_customer_distance_km,
  (customer_lat is not null and seller_lat is not null) has_geolocation,
  case when product_weight_g is not null then product_weight_g/1000.0 end product_weight_kg,
  case when product_length_cm is not null and product_height_cm is not null and product_width_cm is not null then product_length_cm*product_height_cm*product_width_cm/1000000.0 end product_volume_m3
from base;

alter table public.logistics_fact_orders enable row level security;
create index logistics_fact_orders_purchase_date_idx on public.logistics_fact_orders(purchase_date);
create index logistics_fact_orders_od_idx on public.logistics_fact_orders(seller_state,customer_state);
create index logistics_fact_orders_customer_idx on public.logistics_fact_orders(customer_id);
create index logistics_fact_orders_seller_idx on public.logistics_fact_orders(seller_id);
