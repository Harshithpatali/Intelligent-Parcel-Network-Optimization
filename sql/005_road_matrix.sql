create table if not exists public.logistics_road_matrix (
  origin_hub_id integer not null references public.logistics_hubs(hub_id),
  destination_hub_id integer not null references public.logistics_hubs(hub_id),
  distance_km double precision not null,
  travel_time_hours double precision not null,
  routing_engine text not null default 'OSRM',
  profile text not null default 'driving',
  queried_at timestamptz not null default now(),
  is_fallback boolean not null default false,
  primary key(origin_hub_id,destination_hub_id)
);
