-- Step 10: Resilience Intervention Optimization
create table if not exists public.logistics_intervention_plans (
  intervention_id text primary key,
  intervention_type text not null,
  target_hub_id integer,
  target_route_origin_hub_id integer,
  target_route_destination_hub_id integer,
  parameter_name text not null,
  parameter_value double precision not null,
  fixed_cost double precision not null default 0,
  variable_cost double precision not null default 0,
  description text,
  created_at timestamptz not null default now()
);
alter table public.logistics_intervention_plans enable row level security;

create table if not exists public.logistics_intervention_results (
  run_id uuid not null,
  intervention_id text not null,
  forecast_date date not null,
  model_version text not null,
  intervention_cost double precision not null,
  probability_target_met double precision not null,
  service_level_p05 double precision not null,
  service_level_p50 double precision not null,
  service_level_p95 double precision not null,
  unmet_demand_p50 double precision not null,
  unmet_demand_p95 double precision not null,
  transport_cost_p50 double precision not null,
  transport_cost_cvar95 double precision not null,
  risk_reduction double precision,
  service_p50_uplift double precision,
  cost_delta_p50 double precision,
  feasible boolean not null default false,
  created_at timestamptz not null default now(),
  primary key (run_id, intervention_id)
);
alter table public.logistics_intervention_results enable row level security;

create table if not exists public.logistics_intervention_frontier (
  run_id uuid not null,
  intervention_id text not null,
  intervention_cost double precision not null,
  probability_target_met double precision not null,
  service_level_p50 double precision not null,
  unmet_demand_p95 double precision not null,
  transport_cost_p50 double precision not null,
  feasible boolean not null,
  pareto_efficient boolean not null,
  created_at timestamptz not null default now(),
  primary key (run_id, intervention_id)
);
alter table public.logistics_intervention_frontier enable row level security;

create index if not exists intervention_results_forecast_idx
  on public.logistics_intervention_results(forecast_date, model_version);
create index if not exists intervention_frontier_feasible_idx
  on public.logistics_intervention_frontier(feasible, pareto_efficient);