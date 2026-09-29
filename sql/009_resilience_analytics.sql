-- Step 11: production resilience analytics persistence.
-- Safe to run repeatedly against an existing database.

create table if not exists public.logistics_resilience_root_cause (
  run_id uuid not null,
  analysis_type text not null,
  factor text not null,
  factor_level text not null,
  observations integer not null,
  mean_service_level double precision,
  p05_service_level double precision,
  p50_service_level double precision,
  p95_service_level double precision,
  mean_unmet_demand double precision,
  mean_transport_cost double precision,
  contribution_score double precision,
  created_at timestamptz default now(),
  primary key (run_id, analysis_type, factor, factor_level)
);
alter table public.logistics_resilience_root_cause enable row level security;

create index if not exists idx_logistics_root_cause_run
  on public.logistics_resilience_root_cause(run_id, created_at desc);

create table if not exists public.logistics_api_audit (
  request_id text primary key,
  endpoint text not null,
  method text not null,
  status_code integer not null,
  latency_ms double precision,
  created_at timestamptz default now()
);
alter table public.logistics_api_audit enable row level security;

create table if not exists public.logistics_intervention_bundles (
  bundle_id text primary key,
  run_id uuid not null,
  forecast_date date not null,
  model_version text not null,
  budget double precision not null,
  intervention_cost double precision not null,
  probability_target_met double precision not null,
  service_level_p05 double precision,
  service_level_p50 double precision,
  unmet_demand_p95 double precision,
  transport_cost_p50 double precision,
  transport_cost_cvar95 double precision,
  expected_unmet_demand double precision,
  objective_value double precision,
  feasible boolean not null default false,
  pareto_efficient boolean not null default false,
  selected_interventions jsonb not null,
  created_at timestamptz not null default now()
);
alter table public.logistics_intervention_bundles enable row level security;

create index if not exists intervention_bundles_run_idx
  on public.logistics_intervention_bundles(run_id);
create index if not exists intervention_bundles_frontier_idx
  on public.logistics_intervention_bundles(feasible, pareto_efficient);
