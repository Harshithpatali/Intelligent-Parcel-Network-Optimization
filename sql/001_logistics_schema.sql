create extension if not exists postgis;

create table if not exists public.logistics_hubs (
  hub_id text primary key,
  name text,
  lat double precision not null,
  lon double precision not null,
  capacity_parcels bigint not null,
  geom geography(point,4326)
);

create table if not exists public.optimization_runs (
  run_id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  model_version text,
  optimizer_version text,
  status text not null,
  total_transport_cost double precision,
  unmet_demand double precision,
  service_level double precision,
  scenario text
);

alter table public.logistics_hubs enable row level security;
alter table public.optimization_runs enable row level security;
