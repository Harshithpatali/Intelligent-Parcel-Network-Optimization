-- Olist-calibrated candidate hub network. Candidate hubs are inferred from observed ZIP-level demand; they are NOT real carrier facilities.
create extension if not exists postgis;
drop view if exists public.logistics_hub_route_matrix;
drop view if exists public.logistics_hub_od_demand;
drop table if exists public.logistics_hub_assignments;
drop table if exists public.logistics_hubs;
drop table if exists public.logistics_zip_demand;
create table public.logistics_zip_demand as
with customer_d as (select customer_zip_code_prefix zip_code,count(*) parcel_demand from public.logistics_fact_orders where customer_lat between -34 and 6 and customer_lng between -74 and -34 group by 1),
seller_d as (select seller_zip_code_prefix zip_code,count(*) seller_items from public.logistics_fact_orders where seller_lat between -34 and 6 and seller_lng between -74 and -34 group by 1),
geo as (select distinct on (geolocation_zip_code_prefix) geolocation_zip_code_prefix zip_code,geolocation_lat lat,geolocation_lng lng from public.olist_geolocation where geolocation_lat between -34 and 6 and geolocation_lng between -74 and -34 order by geolocation_zip_code_prefix,geolocation_lat,geolocation_lng)
select g.zip_code,g.lat,g.lng,coalesce(c.parcel_demand,0) parcel_demand,coalesce(s.seller_items,0) seller_items,st_setsrid(st_makepoint(g.lng,g.lat),4326) geom
from geo g left join customer_d c using(zip_code) left join seller_d s using(zip_code)
where coalesce(c.parcel_demand,0)+coalesce(s.seller_items,0)>0;
create index logistics_zip_demand_geom_idx on public.logistics_zip_demand using gist(geom);
create table public.logistics_hubs as
with weighted as (select zip_code,lat,lng,parcel_demand,seller_items,st_force4d(st_transform(st_force3d(geom),4978),mvalue=>greatest(1,parcel_demand+seller_items)) geom4 from public.logistics_zip_demand),
clustered as (select *,st_clusterkmeans(geom4,20) over() cluster_id from weighted),
centers as (select cluster_id,sum(parcel_demand) parcel_demand,sum(seller_items) seller_items,st_transform(st_centroid(st_collect(st_transform(geom4,4326))),4326) centroid from clustered group by cluster_id),
nearest as (select c.*,z.zip_code,row_number() over(partition by c.cluster_id order by st_distance(st_transform(st_setsrid(st_makepoint(z.lng,z.lat),4326),3857),st_transform(c.centroid,3857))) rn from centers c join clustered z on z.cluster_id=c.cluster_id)
select row_number() over(order by cluster_id) hub_id,cluster_id,st_y(centroid) lat,st_x(centroid) lng,zip_code representative_zip,parcel_demand,seller_items,round(parcel_demand::numeric/nullif(sum(parcel_demand) over(),0)*100,2) demand_share_pct,st_setsrid(st_makepoint(st_x(centroid),st_y(centroid)),4326) geom
from nearest where rn=1;
create index logistics_hubs_geom_idx on public.logistics_hubs using gist(geom);
create table public.logistics_hub_assignments as
select f.order_id,f.order_item_id,f.seller_id,f.customer_id,f.purchase_date,oh.hub_id origin_hub_id,dh.hub_id destination_hub_id,f.price,f.freight_value,f.product_weight_kg,f.product_volume_m3,f.seller_customer_distance_km
from public.logistics_fact_orders f
cross join lateral (select h.hub_id from public.logistics_hubs h order by h.geom <-> st_setsrid(st_makepoint(f.seller_lng,f.seller_lat),4326) limit 1) oh
cross join lateral (select h.hub_id from public.logistics_hubs h order by h.geom <-> st_setsrid(st_makepoint(f.customer_lng,f.customer_lat),4326) limit 1) dh
where f.seller_lat between -34 and 6 and f.seller_lng between -74 and -34 and f.customer_lat between -34 and 6 and f.customer_lng between -74 and -34;
create index logistics_hub_assignments_date_idx on public.logistics_hub_assignments(purchase_date);
create index logistics_hub_assignments_od_idx on public.logistics_hub_assignments(origin_hub_id,destination_hub_id);
create view public.logistics_hub_od_demand with (security_invoker=true) as
select purchase_date,origin_hub_id,destination_hub_id,count(*) parcel_count,count(distinct order_id) order_count,sum(coalesce(price,0)) item_value,sum(coalesce(freight_value,0)) freight_value,sum(coalesce(product_weight_kg,0)) total_weight_kg,sum(coalesce(product_volume_m3,0)) total_volume_m3,avg(seller_customer_distance_km) avg_seller_customer_distance_km
from public.logistics_hub_assignments group by purchase_date,origin_hub_id,destination_hub_id;
create view public.logistics_hub_route_matrix with (security_invoker=true) as
select a.hub_id origin_hub_id,b.hub_id destination_hub_id,case when a.hub_id=b.hub_id then 0 else st_distance(a.geom::geography,b.geom::geography)/1000.0 end distance_km,case when a.hub_id=b.hub_id then 0 else st_distance(a.geom::geography,b.geom::geography)/1000.0/60.0 end baseline_hours
from public.logistics_hubs a cross join public.logistics_hubs b;