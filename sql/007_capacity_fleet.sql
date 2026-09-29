-- Step 6: calibrated hub capacities + synthetic fleet.
-- Capacities are calibrated from observed Olist throughput. Fleet values are explicit scenario assumptions,
-- not claimed carrier data.

drop table if exists public.logistics_hub_capacity;
create table public.logistics_hub_capacity as
with daily as (
  select purchase_date, hub_id, sum(outbound_parcels)::double precision outbound_parcels,
         sum(inbound_parcels)::double precision inbound_parcels
  from (
    select purchase_date, origin_hub_id hub_id, count(*) outbound_parcels, 0::bigint inbound_parcels
    from public.logistics_hub_assignments group by 1,2
    union all
    select purchase_date, destination_hub_id hub_id, 0::bigint, count(*)::bigint
    from public.logistics_hub_assignments group by 1,2
  ) x
  group by 1,2
),
stats as (
  select hub_id,
    percentile_cont(0.50) within group (order by outbound_parcels) p50_outbound,
    percentile_cont(0.95) within group (order by outbound_parcels) p95_outbound,
    percentile_cont(0.50) within group (order by inbound_parcels) p50_inbound,
    percentile_cont(0.95) within group (order by inbound_parcels) p95_inbound
  from daily group by hub_id
)
select h.hub_id,
       coalesce(s.p50_outbound,0) p50_outbound_parcels,
       coalesce(s.p95_outbound,0) p95_outbound_parcels,
       coalesce(s.p50_inbound,0) p50_inbound_parcels,
       coalesce(s.p95_inbound,0) p95_inbound_parcels,
       greatest(10, ceil(greatest(coalesce(s.p95_outbound,0),coalesce(s.p95_inbound,0))*1.25))::integer capacity_parcels,
       1.25::double precision safety_factor,
       'p95_daily_throughput_x_1.25'::text calibration_method,
       now() created_at
from public.logistics_hubs h left join stats s using(hub_id);

alter table public.logistics_hub_capacity add primary key (hub_id);

drop table if exists public.logistics_fleet;
create table public.logistics_fleet (
  vehicle_type text primary key,
  vehicle_count integer not null check(vehicle_count > 0),
  parcel_capacity integer not null check(parcel_capacity > 0),
  operating_hours_per_day double precision not null check(operating_hours_per_day > 0),
  fixed_trip_cost double precision not null check(fixed_trip_cost >= 0),
  cost_per_km double precision not null check(cost_per_km >= 0),
  max_trip_hours double precision not null check(max_trip_hours > 0),
  assumption_source text not null
);

insert into public.logistics_fleet values
('linehaul_truck', 10, 40, 16.0, 45.0, 0.075, 16.0, 'synthetic scenario assumption'),
('medium_truck',   14, 20, 14.0, 25.0, 0.090, 12.0, 'synthetic scenario assumption'),
('delivery_van',   20,  8, 12.0, 12.0, 0.120,  8.0, 'synthetic scenario assumption');

drop table if exists public.logistics_optimized_flows;
create table public.logistics_optimized_flows (
  run_id uuid not null,
  forecast_date date not null,
  origin_hub integer not null,
  destination_hub integer not null,
  vehicle_type text,
  requested_parcels double precision not null,
  parcels double precision not null,
  unmet_parcels double precision not null,
  trips integer not null,
  distance_km double precision,
  travel_time_hours double precision,
  transport_cost double precision,
  model_version text,
  created_at timestamptz default now()
);
create index logistics_optimized_flows_date_idx on public.logistics_optimized_flows(forecast_date);
create index logistics_optimized_flows_run_idx on public.logistics_optimized_flows(run_id);
